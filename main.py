"""
The Follow Scout - Apify Production Version
===========================================
Instagram Following Tracker with Advanced Session Rotation & Error Handling

Author: AI Assistant
Version: 2.0.0
"""

import os
import random
import json
import time
import logging
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests
import instaloader
from apify_client import ApifyClient

# ==========================================
# 📊 CONFIGURATION & DATA STRUCTURES
# ==========================================

@dataclass
class SessionInfo:
    """Session bilgilerini tutan veri yapısı"""
    session_id: str
    username: str
    is_active: bool = True
    fail_count: int = 0
    last_used: Optional[float] = None

@dataclass
class ScrapeResult:
    """Tarama sonucunu tutan veri yapısı"""
    success: bool
    username: str
    following_list: Optional[List[str]] = None
    error_message: Optional[str] = None
    session_used: Optional[str] = None

# ==========================================
# 🔧 LOGGING SETUP
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# 🔐 SESSION MANAGER (ROTATİON SİSTEMİ)
# ==========================================

class SessionManager:
    """
    Çoklu Instagram session'ları yönetir.
    Bir session fail olduğunda otomatik olarak bir sonrakine geçer.
    """

    MAX_FAIL_COUNT = 3  # Bir session'a max kaç kez güvenilir
    COOLDOWN_SECONDS = 300  # Fail olan session 5 dk beklesin

    def __init__(self, session_configs: List[Dict[str, str]]):
        """
        Args:
            session_configs: [{"session_id": "...", "username": "bot1"}, ...]
        """
        self.sessions: List[SessionInfo] = [
            SessionInfo(
                session_id=config['session_id'],
                username=config.get('username', f'bot_{i}')
            )
            for i, config in enumerate(session_configs)
        ]

        if not self.sessions:
            raise ValueError("❌ En az bir session gerekli!")

        self.current_index = 0
        logger.info(f"✅ SessionManager başlatıldı: {len(self.sessions)} session yüklendi")

    def get_active_session(self) -> Optional[SessionInfo]:
        """
        Kullanılabilir bir session döndürür.
        Tüm session'lar fail ise None döner.
        """
        # Tüm session'ları kontrol et
        available = [s for s in self.sessions if s.is_active and s.fail_count < self.MAX_FAIL_COUNT]

        if not available:
            logger.error("❌ Hiç kullanılabilir session kalmadı!")
            return None

        # Cooldown süresini kontrol et
        now = time.time()
        for session in available:
            if session.last_used:
                elapsed = now - session.last_used
                if elapsed < self.COOLDOWN_SECONDS:
                    continue  # Bu session henüz cooldown'da

            session.last_used = now
            logger.info(f"🔑 Session seçildi: {session.username} (fail_count: {session.fail_count})")
            return session

        # Cooldown'da olmayanları tekrar dene
        session = available[0]
        session.last_used = now
        return session

    def mark_session_failed(self, session: SessionInfo, error_type: str):
        """Session'ı başarısız olarak işaretler"""
        session.fail_count += 1
        logger.warning(
            f"⚠️ Session FAIL: {session.username} "
            f"(fail_count: {session.fail_count}/{self.MAX_FAIL_COUNT}) - Hata: {error_type}"
        )

        if session.fail_count >= self.MAX_FAIL_COUNT:
            session.is_active = False
            logger.error(f"🚫 Session DEVRE DIŞI: {session.username}")

    def mark_session_success(self, session: SessionInfo):
        """Session başarılı olduğunda fail count'u sıfırla"""
        if session.fail_count > 0:
            logger.info(f"✅ Session iyileşti: {session.username}")
            session.fail_count = 0

    def get_stats(self) -> Dict:
        """Session istatistiklerini döndürür"""
        active = sum(1 for s in self.sessions if s.is_active)
        return {
            "total": len(self.sessions),
            "active": active,
            "failed": len(self.sessions) - active
        }

# ==========================================
# 🌐 PROXY MANAGER
# ==========================================

class ProxyManager:
    """Proxy rotation ve validation"""

    def __init__(self, proxy_urls: Optional[List[str]] = None):
        self.proxies = proxy_urls or []
        self.current_index = 0

        if self.proxies:
            logger.info(f"✅ ProxyManager: {len(self.proxies)} proxy yüklendi")
        else:
            logger.warning("⚠️ Proxy kullanılmıyor (riskli!)")

    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Mevcut proxy'yi döndürür"""
        if not self.proxies:
            return None

        proxy = self.proxies[self.current_index]
        return {"http": proxy, "https": proxy}

    def rotate(self):
        """Bir sonraki proxy'ye geç"""
        if self.proxies:
            self.current_index = (self.current_index + 1) % len(self.proxies)
            logger.info(f"🔄 Proxy rotasyonu: {self.current_index + 1}/{len(self.proxies)}")

# ==========================================
# 📥 INSTAGRAM SCRAPER (CORE ENGINE)
# ==========================================

class InstagramScraper:
    """Instagram tarama motoru"""

    RETRY_DELAYS = [30, 60, 120]  # Retry aralıkları (saniye)

    def __init__(
        self,
        session_manager: SessionManager,
        proxy_manager: ProxyManager
    ):
        self.session_mgr = session_manager
        self.proxy_mgr = proxy_manager
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True
        )

    def scrape_following(
        self,
        target_username: str,
        max_retries: int = 3
    ) -> ScrapeResult:
        """
        Bir kullanıcının following listesini çeker.
        Hata durumunda otomatik retry ve session rotation yapar.
        """
        for attempt in range(max_retries):
            session = self.session_mgr.get_active_session()

            if not session:
                return ScrapeResult(
                    success=False,
                    username=target_username,
                    error_message="Tüm session'lar tükendi"
                )

            try:
                # Session ve Proxy Ayarla
                self._configure_loader(session)

                logger.info(
                    f"🔍 [{attempt + 1}/{max_retries}] "
                    f"{target_username} taranıyor (Session: {session.username})"
                )

                # Profili Çek
                profile = instaloader.Profile.from_username(
                    self.loader.context,
                    target_username
                )

                # Rate limit öncesi bekleme
                self._respectful_delay()

                # Following Listesini Çek
                following_list = []
                followees = profile.get_followees()

                # Güvenli iterasyon (maksimum 5000 kişi al, daha fazlası şüpheli)
                for i, followee in enumerate(followees):
                    if i >= 5000:
                        logger.warning(f"⚠️ {target_username}: 5000+ takip tespit edildi, limit konuldu")
                        break
                    following_list.append(followee.username)

                    # Her 50 kişide bir kısa ara
                    if (i + 1) % 50 == 0:
                        time.sleep(random.uniform(1, 3))

                # Başarı
                self.session_mgr.mark_session_success(session)
                logger.info(f"✅ {target_username}: {len(following_list)} kişi çekildi")

                return ScrapeResult(
                    success=True,
                    username=target_username,
                    following_list=following_list,
                    session_used=session.username
                )

            except instaloader.exceptions.ProfileNotExistsException:
                logger.error(f"❌ {target_username}: Profil bulunamadı (silinmiş/gizli)")
                return ScrapeResult(
                    success=False,
                    username=target_username,
                    error_message="Profil mevcut değil"
                )

            except instaloader.exceptions.PrivateProfileNotFollowedException:
                logger.error(f"❌ {target_username}: Profil private ve takip etmiyoruz")
                return ScrapeResult(
                    success=False,
                    username=target_username,
                    error_message="Private profil"
                )

            except instaloader.exceptions.LoginRequiredException:
                logger.error(f"⚠️ Session geçersiz: {session.username}")
                self.session_mgr.mark_session_failed(session, "LoginRequired")
                # Yeni session ile tekrar dene
                continue

            except instaloader.exceptions.ConnectionException as e:
                error_msg = str(e).lower()

                # Rate Limit
                if "429" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"⏳ Rate Limit! Session: {session.username}")
                    self.session_mgr.mark_session_failed(session, "RateLimit")

                    # Retry delay
                    if attempt < len(self.RETRY_DELAYS):
                        delay = self.RETRY_DELAYS[attempt]
                        logger.info(f"⏸️ {delay}s bekleniyor...")
                        time.sleep(delay)
                    continue

                # Checkpoint (Instagram şüphelendi)
                elif "checkpoint" in error_msg:
                    logger.error(f"🚨 CHECKPOINT! Session: {session.username}")
                    self.session_mgr.mark_session_failed(session, "Checkpoint")
                    continue

                # Diğer bağlantı hataları
                else:
                    logger.error(f"❌ Bağlantı hatası: {e}")
                    self.session_mgr.mark_session_failed(session, "ConnectionError")
                    time.sleep(10)
                    continue

            except Exception as e:
                logger.error(f"❌ Beklenmeyen hata ({target_username}): {e}")
                self.session_mgr.mark_session_failed(session, "UnknownError")
                time.sleep(5)
                continue

        # Tüm denemeler başarısız
        return ScrapeResult(
            success=False,
            username=target_username,
            error_message=f"Max retry ({max_retries}) aşıldı"
        )

    def _configure_loader(self, session: SessionInfo):
        """Instaloader'ı session ve proxy ile yapılandır"""
        # Session ID'yi ayarla
        self.loader.context._session.cookies.set('sessionid', session.session_id)
        self.loader.context.username = session.username

        # Proxy ayarla
        proxy_dict = self.proxy_mgr.get_proxy_dict()
        if proxy_dict:
            self.loader.context._session.proxies.update(proxy_dict)

    def _respectful_delay(self):
        """Instagram'ı kızdırmamak için gerçekçi bekleme"""
        delay = random.uniform(3, 8)
        time.sleep(delay)

# ==========================================
# 💾 STATE MANAGER (APIFY KV STORE)
# ==========================================

class StateManager:
    """Apify Key-Value Store üzerinden state yönetimi"""

    STATE_KEY = "STATE"

    def __init__(self, kv_store):
        self.kv_store = kv_store

    def load_previous_state(self) -> Dict[str, List[str]]:
        """Önceki state'i yükle"""
        try:
            record = self.kv_store.get_record(self.STATE_KEY)
            if record and record.get('value'):
                logger.info("✅ Önceki state yüklendi")
                return record['value']
        except Exception as e:
            logger.warning(f"⚠️ State yükleme hatası: {e}")

        return {}

    def save_current_state(self, state: Dict[str, List[str]]):
        """Yeni state'i kaydet"""
        try:
            self.kv_store.set_record(self.STATE_KEY, state)
            logger.info("💾 State buluta kaydedildi")
        except Exception as e:
            logger.error(f"❌ State kaydetme hatası: {e}")

# ==========================================
# 🔍 COMPARISON ENGINE (AKILLI KARŞILAŞTIRMA)
# ==========================================

class ComparisonEngine:
    """
    Following listelerini karşılaştırır.
    ÖNEMLI: Boş liste = hemen 'takipten çıktı' olarak algılamaz!
    """

    MIN_EXPECTED_FOLLOWING = 10  # Bir kullanıcı minimum 10 kişi takip etmeli (validation)

    @staticmethod
    def compare(
        username: str,
        old_list: Optional[List[str]],
        new_list: List[str]
    ) -> Dict:
        """
        İki listeyi karşılaştırır ve değişiklikleri döndürür.

        Returns:
            {
                "has_changes": bool,
                "new_follows": List[str],
                "unfollows": List[str],
                "is_suspicious": bool,  # Yeni liste şüpheli mi?
                "warning": Optional[str]
            }
        """
        result = {
            "has_changes": False,
            "new_follows": [],
            "unfollows": [],
            "is_suspicious": False,
            "warning": None
        }

        # İlk tarama
        if old_list is None:
            logger.info(f"🆕 {username}: İlk tarama (baseline oluşturuluyor)")
            return result

        # VALIDATION: Yeni liste boş veya çok küçük mü?
        if len(new_list) < ComparisonEngine.MIN_EXPECTED_FOLLOWING:
            result["is_suspicious"] = True
            result["warning"] = (
                f"⚠️ {username}: Yeni liste çok küçük ({len(new_list)} kişi). "
                f"Instagram hatası olabilir, değişiklikler göz ardı edildi."
            )
            logger.warning(result["warning"])
            return result

        # Normal karşılaştırma
        old_set = set(old_list)
        new_set = set(new_list)

        new_follows = list(new_set - old_set)
        unfollows = list(old_set - new_set)

        # VALIDATION: Çok fazla takipten çıkma var mı? (şüpheli)
        if len(unfollows) > len(old_list) * 0.5:  # %50'den fazlası gittiyse
            result["is_suspicious"] = True
            result["warning"] = (
                f"⚠️ {username}: Takip listesinin %{int(len(unfollows)/len(old_list)*100)}'i "
                f"kayboldu ({len(unfollows)} kişi). Instagram hatası olabilir!"
            )
            logger.warning(result["warning"])
            return result

        if new_follows or unfollows:
            result["has_changes"] = True
            result["new_follows"] = new_follows
            result["unfollows"] = unfollows
            logger.info(
                f"📊 {username}: "
                f"+{len(new_follows)} yeni, "
                f"-{len(unfollows)} takipten çıkma"
            )
        else:
            logger.info(f"✅ {username}: Değişiklik yok")

        return result

# ==========================================
# 📢 TELEGRAM NOTIFIER
# ==========================================

class TelegramNotifier:
    """Telegram bildirim sistemi"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send_alert(self, message: str, parse_mode: str = "HTML"):
        """Telegram'a mesaj gönder"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.debug("📨 Telegram mesajı gönderildi")
            else:
                logger.error(f"❌ Telegram hatası: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Telegram gönderim hatası: {e}")

    def notify_new_follow(self, target: str, new_person: str):
        """Yeni takip bildirimi"""
        msg = (
            f"🚨 <b>{target}</b> yeni birini takip etti!\n"
            f"👤 <b>{new_person}</b>\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_alert(msg)

    def notify_unfollow(self, target: str, lost_person: str):
        """Takipten çıkma bildirimi"""
        msg = (
            f"📉 <b>{target}</b> takipten çıktı:\n"
            f"❌ <b>{lost_person}</b>\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_alert(msg)

    def notify_error(self, message: str):
        """Hata bildirimi"""
        msg = f"⚠️ <b>HATA</b>\n{message}"
        self.send_alert(msg)

# ==========================================
# 🎯 MAIN ORCHESTRATOR
# ==========================================

def main():
    """Ana orkestrasyon fonksiyonu"""

    logger.info("=" * 60)
    logger.info("🚀 THE FOLLOW SCOUT - BAŞLATILIYOR")
    logger.info("=" * 60)

    try:
        # 1️⃣ Apify Client Başlat
        apify_token = os.environ.get('APIFY_TOKEN')
        if not apify_token:
            raise ValueError("❌ APIFY_TOKEN çevre değişkeni bulunamadı!")

        client = ApifyClient(apify_token)
        kv_store = client.key_value_store()

        # 2️⃣ Input'u Al ve Validate Et
        logger.info("📥 Actor input'u yükleniyor...")
        input_record = kv_store.get_record('INPUT')

        if not input_record or not input_record.get('value'):
            raise ValueError("❌ INPUT bulunamadı!")

        actor_input = input_record['value']

        # Gerekli alanları kontrol et
        targets = actor_input.get('targets', [])
        session_configs = actor_input.get('sessions', [])  # [{"session_id": "...", "username": "bot1"}]
        proxy_urls = actor_input.get('proxy_urls', [])  # Liste halinde
        tg_token = actor_input.get('telegram_token')
        tg_chat_id = actor_input.get('telegram_chat_id')

        # Validation
        if not targets:
            raise ValueError("❌ 'targets' listesi boş!")
        if not session_configs:
            raise ValueError("❌ 'sessions' listesi boş!")
        if not tg_token or not tg_chat_id:
            raise ValueError("❌ Telegram bilgileri eksik!")

        logger.info(f"✅ Input doğrulandı: {len(targets)} hedef, {len(session_configs)} session")

        # 3️⃣ Manager'ları Başlat
        session_mgr = SessionManager(session_configs)
        proxy_mgr = ProxyManager(proxy_urls)
        scraper = InstagramScraper(session_mgr, proxy_mgr)
        state_mgr = StateManager(kv_store)
        notifier = TelegramNotifier(tg_token, tg_chat_id)

        # 4️⃣ Önceki State'i Yükle
        previous_data = state_mgr.load_previous_state()
        current_data = {}

        # 5️⃣ Ana Tarama Döngüsü
        logger.info(f"\n🔍 TARAMA BAŞLIYOR: {len(targets)} hedef\n")

        successful_scrapes = 0
        failed_scrapes = 0

        for i, target_username in enumerate(targets, 1):
            logger.info(f"\n--- [{i}/{len(targets)}] {target_username} ---")

            # Scrape yap
            result = scraper.scrape_following(target_username)

            if not result.success:
                logger.error(f"❌ {target_username}: Tarama başarısız - {result.error_message}")
                failed_scrapes += 1

                # Eski veriyi koru (veri kaybını önle)
                if target_username in previous_data:
                    current_data[target_username] = previous_data[target_username]
                    logger.info(f"💾 {target_username}: Eski veri korundu")

                # Hata bildirimi gönder
                notifier.notify_error(
                    f"<b>{target_username}</b> taranamadı:\n{result.error_message}"
                )
                continue

            # Başarılı tarama
            successful_scrapes += 1
            following_list = result.following_list
            current_data[target_username] = following_list

            # 6️⃣ Karşılaştırma Yap
            comparison = ComparisonEngine.compare(
                target_username,
                previous_data.get(target_username),
                following_list
            )

            # Şüpheli durum varsa uyar
            if comparison["is_suspicious"]:
                notifier.notify_error(comparison["warning"])
                continue

            # Değişiklik varsa bildir
            if comparison["has_changes"]:
                # Yeni takipler
                for new_person in comparison["new_follows"]:
                    notifier.notify_new_follow(target_username, new_person)

                # Takipten çıkanlar
                for lost_person in comparison["unfollows"]:
                    notifier.notify_unfollow(target_username, lost_person)

            # Hedefler arası bekleme (Instagram'ı kızdırmamak için)
            if i < len(targets):
                delay = random.uniform(10, 20)
                logger.info(f"⏸️ Sonraki hedef için {delay:.1f}s bekleniyor...")
                time.sleep(delay)

        # 7️⃣ State'i Kaydet
        state_mgr.save_current_state(current_data)

        # 8️⃣ Özet Rapor
        logger.info("\n" + "=" * 60)
        logger.info("📊 TARAMA TAMAMLANDI - ÖZET RAPOR")
        logger.info("=" * 60)
        logger.info(f"✅ Başarılı: {successful_scrapes}/{len(targets)}")
        logger.info(f"❌ Başarısız: {failed_scrapes}/{len(targets)}")

        session_stats = session_mgr.get_stats()
        logger.info(f"🔑 Session Durumu: {session_stats['active']}/{session_stats['total']} aktif")
        logger.info("=" * 60)

        # 9️⃣ Apify Output (İsteğe bağlı)
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "targets_scraped": len(targets),
            "successful": successful_scrapes,
            "failed": failed_scrapes,
            "session_stats": session_stats
        }
        kv_store.set_record('OUTPUT', output_data)

        logger.info("✅ Actor başarıyla tamamlandı!")

    except Exception as e:
        logger.error(f"💥 FATAL ERROR: {e}", exc_info=True)

        # Telegram'a kritik hata bildirimi
        try:
            notifier = TelegramNotifier(
                os.environ.get('TELEGRAM_TOKEN', ''),
                os.environ.get('TELEGRAM_CHAT_ID', '')
            )
            notifier.notify_error(f"KRITIK HATA:\n{str(e)[:200]}")
        except:
            pass

        raise

# ==========================================
# 🏁 ENTRY POINT
# ==========================================

if __name__ == "__main__":
    main()
