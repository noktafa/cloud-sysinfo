#!/usr/bin/env python3
"""
Cloud System Info Analyzer
- DigitalOcean'da droplet oluşturur
- SSH ile sistem bilgisi scriptini çalıştırır
- Sonuçları OpenAI'a gönderip analiz alır
- Droplet'i otomatik siler
"""

import io
import json
import os
import sys
import time

import paramiko
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

DO_TOKEN = os.getenv("DIGITALOCEAN_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

DO_API = "https://api.digitalocean.com/v2"
DO_HEADERS = {
    "Authorization": f"Bearer {DO_TOKEN}",
    "Content-Type": "application/json",
}

REGION = "fra1"
SIZE = "s-1vcpu-512mb-10gb"
IMAGE = "ubuntu-24-04-x64"


def log(msg):
    print(f"[*] {msg}")


def do_request(method, path, **kwargs):
    resp = requests.request(method, f"{DO_API}/{path}", headers=DO_HEADERS, **kwargs)
    if resp.status_code >= 400:
        print(f"[!] DO API hatası ({resp.status_code}): {resp.text}")
        sys.exit(1)
    return resp.json() if resp.content else {}


# --- SSH Key ---

def create_ssh_key():
    log("SSH key pair oluşturuluyor...")
    key = paramiko.RSAKey.generate(4096)
    pub_key = f"ssh-rsa {key.get_base64()} cloud-sysinfo-temp"

    log("SSH key DigitalOcean'a yükleniyor...")
    data = do_request("POST", "account/keys", json={
        "name": "cloud-sysinfo-temp",
        "public_key": pub_key,
    })
    key_id = data["ssh_key"]["id"]
    log(f"SSH key oluşturuldu (ID: {key_id})")
    return key, key_id


def delete_ssh_key(key_id):
    log(f"SSH key siliniyor (ID: {key_id})...")
    requests.delete(f"{DO_API}/account/keys/{key_id}", headers=DO_HEADERS)


# --- Droplet ---

def create_droplet(ssh_key_id):
    log(f"Droplet oluşturuluyor ({REGION}, {SIZE})...")
    data = do_request("POST", "droplets", json={
        "name": "sysinfo-test",
        "region": REGION,
        "size": SIZE,
        "image": IMAGE,
        "ssh_keys": [ssh_key_id],
        "tags": ["cloud-sysinfo"],
    })
    droplet_id = data["droplet"]["id"]
    log(f"Droplet oluşturuldu (ID: {droplet_id})")
    return droplet_id


def wait_for_droplet(droplet_id, timeout=180):
    log("Droplet'in hazır olması bekleniyor...")
    start = time.time()
    while time.time() - start < timeout:
        data = do_request("GET", f"droplets/{droplet_id}")
        droplet = data["droplet"]
        status = droplet["status"]

        if status == "active":
            for net in droplet["networks"]["v4"]:
                if net["type"] == "public":
                    ip = net["ip_address"]
                    log(f"Droplet hazır! IP: {ip}")
                    return ip

        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(5)

    print("\n[!] Droplet zaman aşımına uğradı!")
    sys.exit(1)


def delete_droplet(droplet_id):
    log(f"Droplet siliniyor (ID: {droplet_id})...")
    requests.delete(f"{DO_API}/droplets/{droplet_id}", headers=DO_HEADERS)
    log("Droplet silindi.")


# --- SSH & Script ---

def run_sysinfo_on_droplet(ip, private_key):
    log(f"SSH ile {ip} adresine bağlanılıyor...")

    script_path = os.path.join(os.path.dirname(__file__), "sysinfo.py")
    with open(script_path) as f:
        script_content = f.read()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH bağlantısı için birkaç deneme (droplet henüz SSH kabul etmiyor olabilir)
    for attempt in range(12):
        try:
            client.connect(ip, username="root", pkey=private_key, timeout=10)
            log("SSH bağlantısı kuruldu.")
            break
        except Exception:
            if attempt == 11:
                print("[!] SSH bağlantısı kurulamadı!")
                sys.exit(1)
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(10)

    # Script'i yükle
    log("sysinfo.py yükleniyor...")
    sftp = client.open_sftp()
    with sftp.file("/tmp/sysinfo.py", "w") as f:
        f.write(script_content)
    sftp.close()

    # Çalıştır
    log("sysinfo.py çalıştırılıyor...")
    stdin, stdout, stderr = client.exec_command("python3 /tmp/sysinfo.py")
    output = stdout.read().decode()
    errors = stderr.read().decode()
    client.close()

    if errors:
        log(f"Script uyarıları: {errors}")

    return output


# --- OpenAI ---

def analyze_with_openai(sysinfo_json):
    log("Sistem bilgileri OpenAI'a gönderiliyor...")

    client = OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Sen bir sistem yöneticisi uzmanısın. Sana bir sunucunun "
                    "sistem bilgileri JSON formatında verilecek. Bu bilgileri analiz et, "
                    "Türkçe olarak yorumla. Sunucunun genel durumunu değerlendir, "
                    "varsa potansiyel sorunları belirt ve optimizasyon önerileri sun."
                ),
            },
            {
                "role": "user",
                "content": f"Sunucu sistem bilgileri:\n```json\n{sysinfo_json}\n```",
            },
        ],
    )

    return response.choices[0].message.content


# --- Main ---

def main():
    if not DO_TOKEN or not OPENAI_KEY:
        print("[!] .env dosyasında DIGITALOCEAN_TOKEN ve OPENAI_API_KEY tanımlı olmalı!")
        sys.exit(1)

    print("=" * 60)
    print("  Cloud System Info Analyzer")
    print("=" * 60)
    print()

    droplet_id = None
    ssh_key_id = None

    try:
        # 1. SSH key oluştur
        private_key, ssh_key_id = create_ssh_key()

        # 2. Droplet oluştur
        droplet_id = create_droplet(ssh_key_id)

        # 3. Droplet'in hazır olmasını bekle
        ip = wait_for_droplet(droplet_id)

        # 4. SSH ile script çalıştır
        sysinfo_output = run_sysinfo_on_droplet(ip, private_key)

        print()
        print("-" * 60)
        print("  Sistem Bilgileri (JSON)")
        print("-" * 60)
        sysinfo = json.loads(sysinfo_output)
        print(json.dumps(sysinfo, indent=2, ensure_ascii=False))

        # 5. OpenAI'a gönder
        print()
        print("-" * 60)
        print("  OpenAI Analizi")
        print("-" * 60)
        analysis = analyze_with_openai(sysinfo_output)
        print(analysis)

    finally:
        # 6. Temizlik
        print()
        print("-" * 60)
        print("  Temizlik")
        print("-" * 60)
        if droplet_id:
            delete_droplet(droplet_id)
        if ssh_key_id:
            delete_ssh_key(ssh_key_id)
        log("Tüm kaynaklar temizlendi.")

    print()
    print("=" * 60)
    print("  Tamamlandı!")
    print("=" * 60)


if __name__ == "__main__":
    main()
