import ssl
import aiohttp

# 1. Antivirüs ve Windows SSL engellerini aşan bağlam
ctx_unverified = ssl.create_default_context()
ctx_unverified.check_hostname = False
ctx_unverified.verify_mode = ssl.CERT_NONE

_original_wrap = aiohttp.connector.TCPConnector._wrap_create_connection
async def _patched_wrap(self, *args, **kwargs):
    if kwargs.get('ssl') is not None:
        kwargs['ssl'] = ctx_unverified
    return await _original_wrap(self, *args, **kwargs)

aiohttp.connector.TCPConnector._wrap_create_connection = _patched_wrap

# 2. Discord Kütüphanesini Başlatma
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 3. Atık Veritabanı
ATIK_REHBERI = {
    "plastik": {
        "baslik": "Plastik Atıklar (PET Şişeler, Ambalajlar)",
        "kutu": "Sarı Geri Dönüşüm Kutusu",
        "ayristirma": "İçindeki sıvı ve kalıntıları boşaltıp çalkalayın. Hacim küçültmek için ezin. Yağlı veya yoğun kirli plastikleri evsel çöpe atın.",
        "arama_terimi": "Plastik geri dönüşümü"
    },
    "cam": {
        "baslik": "Cam Şişe ve Kavanozlar",
        "kutu": "Yeşil / Beyaz Cam Kumbarası",
        "ayristirma": "Kapakları (metal/plastik) çıkartıp ilgili kutulara atın. Şişeleri kırmadan kumbaraya bırakın. Isıya dayanıklı borcam veya aynalar bu kumbaraya atılmaz.",
        "arama_terimi": "Cam geri dönüşümü"
    },
    "elektronik": {
        "baslik": "Piller ve Elektronik Atıklar (AEEE)",
        "kutu": "Atık Pil Kutusu / E-Atık Toplama Noktaları",
        "ayristirma": "Normal çöpe kesinlikle atılmamalıdır! Ağır metal içerir. Marketlerdeki TAP kutularına veya belediye atık merkezlerine teslim edilmelidir.",
        "arama_terimi": "Elektronik atık"
    },
    "kagit": {
        "baslik": "Kağıt ve Karton Ambalajlar",
        "kutu": "Mavi Geri Dönüşüm Kutusu",
        "ayristirma": "Kuru ve temiz olmalıdır. Yağlı pizza kutuları, faturasız fişler veya ıslak mendiller geri dönüştürülemez, evsel çöpe gitmelidir.",
        "arama_terimi": "Kağıt geri dönüşümü"
    },
    "organik": {
        "baslik": "Organik / Biyo-bozunur Atıklar (Meyve, Sebze)",
        "kutu": "Kahverengi Kutu / Kompost Alanı",
        "ayristirma": "Plastik poşet veya yabancı madde karıştırmadan kompost yapılabilir veya biyolojik atık kutusuna atılabilir.",
        "arama_terimi": "Kompost"
    }
}

# 4. İnternetten Özet Bilgi Çekme
async def fetch_cevre_bilgisi(arama_terimi: str) -> str:
    url = f"https://tr.wikipedia.org/api/rest_v1/page/summary/{arama_terimi.replace(' ', '_')}"
    headers = {"User-Agent": "DiscordCevreBotu/1.0"}
    
    try:
        connector = aiohttp.TCPConnector(ssl=ctx_unverified)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("extract", "Detaylı çevre bilgisi bulunamadı.")
                return "Bu madde hakkında harici kaynakta ek özet bulunamadı."
    except Exception:
        return "İnternet üzerinden ek bilgi alınırken bir bağlantı hatası oluştu."

# 5. Discord Arayüz Bileşenleri (Select Menu)
class AtikSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Plastik", value="plastik", description="Şişeler, poşetler, kaplar", emoji="🧴"),
            discord.SelectOption(label="Cam", value="cam", description="Şişe, kavanoz, cam kaplar", emoji="🍾"),
            discord.SelectOption(label="Pil ve E-Atık", value="elektronik", description="Piller, kablolar, elektronik cihazlar", emoji="🔋"),
            discord.SelectOption(label="Kağıt / Karton", value="kagit", description="Kutular, gazeteler, defterler", emoji="📦"),
            discord.SelectOption(label="Organik Atık", value="organik", description="Meyve kabukları, yemek artıkları", emoji="🍎")
        ]
        super().__init__(placeholder="Bilgi almak istediğiniz atık türünü seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        secilen_anahtar = self.values[0]
        atik_verisi = ATIK_REHBERI.get(secilen_anahtar)

        await interaction.response.defer()

        ek_bilgi = await fetch_cevre_bilgisi(atik_verisi["arama_terimi"])

        embed = discord.Embed(
            title=f"♻️ {atik_verisi['baslik']}",
            color=discord.Color.green()
        )
        embed.add_field(name="🗑️ Doğru Atık Kutusu", value=f"**{atik_verisi['kutu']}**", inline=False)
        embed.add_field(name="🛠️ Nasıl Ayrıştırılmalı?", value=atik_verisi["ayristirma"], inline=False)
        embed.add_field(name="🌍 Çevre ve Süreç Bilgisi", value=ek_bilgi[:600] + ("..." if len(ek_bilgi) > 600 else ""), inline=False)
        embed.set_footer(text="Geri dönüşüme katkı sağladığınız için teşekkürler!")

        await interaction.followup.send(embed=embed)

class AtikView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(AtikSelect())

# 6. Bot Olayları ve Komutları
@bot.event
async def on_ready():
    print(f"Bot başarıyla aktif oldu: {bot.user.name} ({bot.user.id})")

@bot.command(name="atık", aliases=["atik"])
async def atik_komutu(ctx):
    view = AtikView()
    await ctx.send("Lütfen ayrıştırma ve çevre bilgisine ulaşmak istediğiniz atık türünü seçin:", view=view)

# Reset Token diyerek aldığınız YENİ tokeni aşağıdaki tırnakların içine yapıştırın:
bot.run("TOKENİ_BURAYA_YAZIN")
