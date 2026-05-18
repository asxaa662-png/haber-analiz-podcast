import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import asyncio
import edge_tts
import io
from groq import Groq

st.set_page_config(page_title="Haber Analiz Podcast", page_icon="🎙️")
st.title("🎙️ Haber Analiz Podcast")
st.markdown("Haberi yapıştır — derin analiz yap, gerçekçi 2 kişilik podcast üret!")

AYSE_SES = "tr-TR-EmelNeural"
MERT_SES = "tr-TR-AhmetNeural"

groq_api_key = st.text_input(
    "🔑 Groq API Anahtarı:",
    type="password",
    placeholder="gsk_xxxx...",
    help="console.groq.com adresinden ücretsiz al"
)

url = st.text_input("🔗 Haber URL'si:")

def metni_cek(url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "button", "iframe", "img"]):
            tag.decompose()
        paragraflar = soup.find_all("p")
        metin = " ".join(p.get_text(strip=True) for p in paragraflar)
        if len(metin) < 200:
            metin = soup.get_text(separator=" ", strip=True)
        metin = re.sub(r"\s+", " ", metin).strip()
        return metin if len(metin) > 100 else None
    except Exception as e:
        st.error(f"Metin çekme hatası: {e}")
        return None

def diyalog_uret(metin, api_key):
    client = Groq(api_key=api_key)
    sistem = """Sen deneyimli bir podcast yazarısın.
Sana verilen haber metnini analiz edip iki sunucu arasında
geçen doğal, samimi ve derinlikli bir Türkçe podcast diyalogu yazıyorsun.

ÇIKTI FORMATI (sadece bu satırları yaz, başka hiçbir şey yazma):
AYŞE: [metin]
MERT: [metin]
AYŞE: [metin]
...

KURALLAR:
- Tam olarak 10-14 satır yaz
- AYŞE meraklı, soru soran, zaman zaman şaşıran kadın sunucu
- MERT analitik, bağlam kuran, yer yer eleştirel erkek sunucu
- Haberin sadece özetini değil; arka planını, önemini, olası sonuçlarını da konuş
- "Peki bunu neden önemseyelim?", "Yani şu anlama mı geliyor?" tarzı sorular sor
- Doğal geçişler: "Evet ama...", "Bir saniye...", "Şöyle düşün..." gibi ifadeler kullan
- Resmi değil samimi konuş, ama yüzeysel de olma
- Başlangıçta kısa bir giriş, sonda kısa bir kapanış olsun"""

    kullanici = f"Şu haberi analiz et ve podcast diyalogu oluştur:\n\n{metin[:3000]}"

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": sistem},
                {"role": "user", "content": kullanici}
            ],
            max_tokens=2000,
            temperature=0.85
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Groq API hatası: {e}")
        return None

def diyalogi_parcala(diyalog):
    satirlar = []
    for satir in diyalog.strip().split("\n"):
        satir = satir.strip()
        if not satir:
            continue
        if re.match(r"^AYŞE\s*:", satir, re.IGNORECASE) or re.match(r"^AYSE\s*:", satir, re.IGNORECASE):
            metin = re.sub(r"^AYŞE\s*:|^AYSE\s*:", "", satir, flags=re.IGNORECASE).strip()
            if metin:
                satirlar.append(("ayse", metin))
        elif re.match(r"^MERT\s*:", satir, re.IGNORECASE):
            metin = re.sub(r"^MERT\s*:", "", satir, flags=re.IGNORECASE).strip()
            if metin:
                satirlar.append(("mert", metin))
    return satirlar

async def podcast_olustur_async(satirlar):
    """Her satırı Edge TTS ile sese çevirip WAV bytes olarak birleştirir."""
    tum_ses = b""
    sessizlik = b"\x00" * 8000  # ~0.25sn sessizlik (raw PCM yaklaşımı)

    parcalar = []
    for konusmaci, metin in satirlar:
        ses_adi = AYSE_SES if konusmaci == "ayse" else MERT_SES
        try:
            communicate = edge_tts.Communicate(metin, ses_adi)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            buf.seek(0)
            parcalar.append(buf.read())
        except Exception as e:
            st.warning(f"Bir satır atlandı: {e}")
            continue

    # MP3 parçalarını arka arkaya birleştir (basit binary concat)
    # Edge TTS MP3 çıktıları doğrudan birleştirilebilir
    birlesik = b"".join(parcalar)
    return io.BytesIO(birlesik)

def podcast_olustur(satirlar):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(podcast_olustur_async(satirlar))
    except Exception as e:
        st.error(f"Ses oluşturma hatası: {e}")
        return None

if st.button("🚀 Analiz Et ve Podcast Oluştur", type="primary"):
    if not groq_api_key.strip():
        st.warning("Lütfen Groq API anahtarını gir.")
    elif not url.strip():
        st.warning("Lütfen bir haber URL'si gir.")
    else:
        with st.spinner("📰 Haber metni çekiliyor..."):
            metin = metni_cek(url)

        if not metin:
            st.error("❌ Bu sayfadan metin çekemedim. Farklı bir URL deneyin.")
        else:
            st.success(f"✅ Metin çekildi — {len(metin)} karakter")
            with st.expander("📄 Ham Metni Gör"):
                st.write(metin[:2000] + ("..." if len(metin) > 2000 else ""))

            with st.spinner("🧠 Haber analiz ediliyor, diyalog yazılıyor..."):
                diyalog = diyalog_uret(metin, groq_api_key)

            if not diyalog:
                st.error("❌ Diyalog oluşturulamadı.")
            else:
                st.success("✅ Diyalog hazır!")
                with st.expander("💬 Podcast Diyaloğunu Gör"):
                    st.text(diyalog)

                satirlar = diyalogi_parcala(diyalog)

                if not satirlar:
                    st.error("❌ Diyalog formatı okunamadı, tekrar deneyin.")
                    st.text(diyalog)
                else:
                    st.info(f"🎙️ {len(satirlar)} konuşma satırı bulundu...")

                    with st.spinner("🔊 Sesler oluşturuluyor..."):
                        ses = podcast_olustur(satirlar)

                    if ses:
                        st.success("🎙️ Podcast hazır!")
                        st.audio(ses, format="audio/mp3")
                        st.download_button(
                            label="⬇️ MP3 İndir",
                            data=ses,
                            file_name="podcast.mp3",
                            mime="audio/mp3"
                        )

st.markdown("---")
st.caption("Groq (Llama3-70B) + Microsoft Edge TTS — tamamen ücretsiz")