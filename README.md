# 🔍 The Follow Scout

**Instagram Takip Değişikliği Takipçisi** - Hedef kullanıcıların takip listelerindeki değişiklikleri gerçek zamanlı izler ve Telegram'a bildirim gönderir.

## 🎯 Özellikler

- ✅ Çoklu hedef kullanıcı takibi
- ✅ Otomatik session rotation (bir session ban yerse diğerine geçer)
- ✅ Proxy desteği (residential proxy önerilir)
- ✅ Rate limit koruması
- ✅ Akıllı hata algılama (Instagram bug'larını filtreler)
- ✅ Telegram gerçek zamanlı bildirimler
- ✅ State persistence (tarama geçmişi bulutta saklanır)

## 📥 Input Parametreleri

```json
{
  "targets": ["cristiano", "leomessi"],
  "sessions": [
    {
      "session_id": "123456789%3A...",
      "username": "bot_account1"
    }
  ],
  "proxy_urls": [
    "http://user:pass@proxy.com:8000"
  ],
  "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "telegram_chat_id": "123456789"
}
```

### Gerekli Parametreler

- **targets**: İzlenecek Instagram kullanıcı adları (array)
- **sessions**: Bot hesaplarının Instagram session bilgileri (en az 1 tane)
  - `session_id`: Instagram cookies'den alınan sessionid değeri
  - `username`: Bot hesabının kullanıcı adı
- **telegram_token**: Telegram bot token (BotFather'dan alın)
- **telegram_chat_id**: Bildirim gönderilecek Telegram chat ID

### Opsiyonel Parametreler

- **proxy_urls**: Residential proxy listesi (önerilir)

## 🚀 Nasıl Kullanılır?

### 1. Instagram Session ID Alma

```bash
# Chrome/Firefox Developer Tools:
# 1. Instagram'a giriş yapın
# 2. F12 tuşuna basın
# 3. Application > Cookies > https://www.instagram.com
# 4. "sessionid" değerini kopyalayın
```

### 2. Telegram Bot Kurulumu

```bash
# 1. @BotFather'a mesaj atın
# 2. /newbot komutu ile bot oluşturun
# 3. Token'ı kaydedin
# 4. @userinfobot'a mesaj atarak chat ID'nizi öğrenin
```

### 3. Apify'da Schedule Ayarlama

Actor'ı **5-10 dakikada bir** çalışacak şekilde schedule edin:

```
Schedule: */5 * * * *  (her 5 dakikada bir)
```

## 🛡️ Güvenlik Notları

- ⚠️ Ana Instagram hesabınızın session'ını kullanmayın!
- ✅ Dummy bot hesapları oluşturun
- ✅ Her bot hesabı için farklı proxy kullanın
- ✅ Session'ları düzenli olarak yenileyin

## 📊 Output

Actor her çalıştığında:
- Değişiklikleri Telegram'a bildirir
- State'i buluta kaydeder (bir sonraki çalıştırmada karşılaştırma için)
- Özet raporu Key-Value Store'a yazar

## 🔧 Teknik Detaylar

- **Dil**: Python 3.11
- **Framework**: Instaloader + Apify SDK
- **State Management**: Apify Key-Value Store
- **Rate Limit**: Akıllı bekleme algoritması ile korunur

## 🆘 Sorun Giderme

### "LoginRequired" Hatası
- Session süresi dolmuş, yeni session ID alın

### "RateLimit" Hatası
- Daha fazla bot hesabı ekleyin veya çalıştırma sıklığını azaltın

### "Checkpoint" Hatası
- Instagram şüphelendi, bot hesabını doğrulamanız gerekebilir

## 📝 Lisans

MIT License - Eğitim amaçlıdır.

---

**⚠️ UYARI**: Bu tool sadece eğitim amaçlıdır. Instagram ToS'a aykırı kullanımdan sorumluluk kabul etmiyoruz.
