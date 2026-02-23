# Cloud System Info Analyzer

DigitalOcean droplet üzerinde sistem bilgilerini toplayıp OpenAI ile analiz eden Python projesi.

## Ne Yapar?

1. DigitalOcean'da geçici bir droplet oluşturur
2. SSH ile bağlanıp sistem bilgisi scriptini çalıştırır
3. Toplanan bilgileri OpenAI'a gönderip Türkçe analiz alır
4. Droplet'i ve SSH key'i otomatik siler

## Toplanan Sistem Bilgileri

- OS (dağıtım, kernel, mimari)
- CPU (model, çekirdek sayısı, yük ortalaması)
- RAM (toplam, kullanılan, boş, kullanım yüzdesi)
- Disk (bölümler, boyut, kullanım)
- Ağ (hostname, IP adresi)
- Uptime

## Kurulum

```bash
git clone https://github.com/noktafa/cloud-sysinfo.git
cd cloud-sysinfo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Yapılandırma

Proje kök dizininde `.env` dosyası oluşturun:

```
DIGITALOCEAN_TOKEN=dop_v1_...
OPENAI_API_KEY=sk-proj-...
```

## Kullanım

```bash
source venv/bin/activate
python main.py
```

## Varsayılan Ayarlar

| Ayar | Değer |
|------|-------|
| Region | fra1 (Frankfurt) |
| Droplet boyutu | s-1vcpu-512mb-10gb |
| İmaj | Ubuntu 24.04 |
| OpenAI modeli | gpt-4o-mini |

## Proje Yapısı

```
cloud-sysinfo/
├── .env               # API tokenları (git'e dahil değil)
├── .gitignore
├── main.py            # Orkestratör: droplet → SSH → OpenAI → temizlik
├── requirements.txt
├── sysinfo.py         # Droplet'te çalışan sistem bilgisi scripti
└── README.md
```
