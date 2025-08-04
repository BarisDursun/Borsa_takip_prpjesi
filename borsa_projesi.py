import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time


class BorsaUygulamasi:
    def __init__(self):
        self.bist100_hisseleri = [
            "THYAO.IS", "GARAN.IS", "AKBNK.IS", "ASELS.IS", "KRDMD.IS",
            "SASA.IS", "EREGL.IS", "KCHOL.IS", "TUPRS.IS", "BIMAS.IS","KAYSE.IS"
        ]

    def hisse_verisi_cek(self, hisse_kodu, period):
      ticker = yf.Ticker(hisse_kodu)
      data = ticker.history(period=period)
      return data

    def hisse_bilgileri(self, hisse_kodu):
      ticker = yf.Ticker(hisse_kodu)
      return {
                'isim': ticker.info["longName"],
                'sektor': ticker.info["sector"],
                'piyasa_degeri': ticker.info["marketCap"],
                'fiyat': ticker.info["regularMarketPrice"],
                'değişim': ticker.info["regularMarketChangePercent"]
            }

    def bist100_endeksi(self):
       bist100 = yf.Ticker("^XU100")
       data = bist100.history("1y")
       return data

    def hisse_listesi_goster(self):
        print("📊 BIST100'den Popüler Hisseler:")
        print("-" * 50)

        for i, hisse in enumerate(self.bist100_hisseleri, 1):
            bilgi = self.hisse_bilgileri(hisse)
            if bilgi:
                print(f"{i:2d}. {bilgi['isim']} ({hisse})")
                print(f"    Fiyat: {bilgi['fiyat']:.2f} TL")
                print(f"    Değişim: {bilgi['değişim']:.2f}%")
                print()

    def hisse_grafik_ciz(self, hisse_kodu, period):
        """Hisse fiyat grafiği çizer"""
        data = self.hisse_verisi_cek(hisse_kodu, period)
        if data is not None and not data.empty:
            fig=plt.figure(figsize=(12, 6))
            axes=fig.add_axes([0.1,0.1,0.8,0.8])
            axes.plot(data.index, data['Close'], linewidth=2)  #index tarihi verir x için
            axes.set_title(f"{hisse_kodu} Hisse Fiyat Grafiği")
            axes.set_xlabel("Tarih")
            axes.set_ylabel("Fiyat")
            axes.grid(True, alpha=0.3)  #mouse harejketlerine yarar
            axes.tick_params(axis='x', labelrotation=45) #x dekileri 45 derece döndürür okunulabilirlik için
            plt.tight_layout()
            plt.show()
        else:
            print(f"{hisse_kodu} için veri bulunamadı.")

    def portfoy_analizi(self, hisseler_lotlar):
        print("📈 Portföy Analizi")
        print("-" * 30)

        toplam_deger = 0
        for hisse, lot in hisseler_lotlar:
            bilgi = self.hisse_bilgileri(hisse)
            if bilgi:
                deger = bilgi["fiyat"] * lot
                print(f"{hisse}: {bilgi['fiyat']:.2f} TL × {lot} lot = {deger:.2f} TL")
                toplam_deger += deger
            else:
                print(f"{hisse} için bilgi bulunamadı.")

        print(f"\nToplam Portföy Değeri: {toplam_deger:.2f} TL")

    def canli_takip(self, hisse_kodu, sure_dakika=5):
        print(f"🔴 {hisse_kodu} Canlı Takip (Çıkmak için Ctrl+C)")
        print("-" * 40)

        try:
            for i in range(sure_dakika * 12):  # 5 saniyede bir güncelleme
                ticker = yf.Ticker(hisse_kodu)
                fiyat = ticker.info["regularMarketPrice"]
                değişim = ticker.info["regularMarketChangePercent"]

                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] {hisse_kodu}: {fiyat:.2f} TL ({değişim:+.2f}%)",end="") #ende aynı satırda
                print("Çıkmak için 'q' tuşuna basın, devam etmek için Enter'a basın.")
                cevap = input()
                if cevap.lower() == 'q':
                    print("Takip sonlandırıldı.")
                    break

                time.sleep(5)

        except :
            print("\n\nTakip sonlandırıldı.")


def main():
    uygulama = BorsaUygulamasi()

    while True:
        print("\n" + "=" * 50)
        print("📊 BORSA UYGULAMASI")
        print("=" * 50)
        print("1. Hisse Listesi")
        print("2. Hisse Grafiği")
        print("3. BIST100 Endeksi")
        print("4. Portföy Analizi")
        print("5. Canlı Takip")
        print("6. Çıkış")
        print("-" * 50)

        secim = input("Seçiminizi yapın (1-6): ")

        if secim == "1":
            uygulama.hisse_listesi_goster()

        elif secim == "2":
            print("\nMevcut hisseler:")
            for i, hisse in enumerate(uygulama.bist100_hisseleri[:10], 1):  #kaçıncı sıra olduğunuda biliriz 1 den başlatdık
                print(f"{i}. {hisse}")
            hisse_no = int(input("\nHangi hissenin grafiğini görmek istiyorsunuz? (1-10): ")) - 1
            if 0 <= hisse_no < len(uygulama.bist100_hisseleri):
                uygulama.hisse_grafik_ciz(uygulama.bist100_hisseleri[hisse_no],period="1y")
            else:
                    print("Geçersiz seçim!")


        elif secim == "3":
            bist100 = yf.Ticker("^XU100")
            degisim = bist100.info.get("regularMarketChangePercent")
            fiyat = bist100.info.get("regularMarketPrice")

            if degisim is not None and fiyat is not None:
                print(f"\n📈 BIST100 Endeksi")
                print(f"Son Fiyat: {fiyat:.2f}")
                print(f"Günlük Değişim: {degisim:+.2f}%")
            else:
                print("BIST100 bilgileri alınamadı.")



        elif secim == "4":
            print("\nPortföyünüzdeki hisseleri ve lot miktarlarını girin (virgülle ayırın):")
            print("Örnek: THYAO.IS:10,GARAN.IS:5,AKBNK.IS:20")
            giris = input("Hisseler ve lotlar: ")
            hisseler_lotlar = []
            for parca in giris.split(','):
                try:
                    hisse, lot = parca.split(':')
                    lot = int(lot.strip())
                    hisseler_lotlar.append((hisse.strip(), lot))
                except:
                    print(f"Hatalı giriş: '{parca}'. Bu hisse atlanacak.")
            uygulama.portfoy_analizi(hisseler_lotlar)
        elif secim == "5":
            hisse = input("Takip edilecek hisse kodunu girin (örn: THYAO.IS): ")
            sure = int(input("Takip süresi (dakika): "))
            uygulama.canli_takip(hisse, sure)

        elif secim == "6":
            print("Uygulama kapatılıyor...")
            break

        else:
            print("Geçersiz seçim! Lütfen 1-6 arası bir sayı girin.")


if __name__ == "__main__":
    main()