import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time
import os
import mysql.connector
import pandas as pd


class BorsaUygulamasi:
    def __init__(self):
        self.bist100_hisseleri = [
            "THYAO.IS", "GARAN.IS", "AKBNK.IS", "ASELS.IS", "KRDMD.IS",
            "SASA.IS", "EREGL.IS", "KCHOL.IS", "TUPRS.IS", "BIMAS.IS","KAYSE.IS"
        ]
        self.db_conn = None
        self._db_connect()
        self._ensure_tables()

    def _db_connect(self):
        try:
            self.db_conn = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "127.0.0.1"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", "4340"),
                database=os.getenv("MYSQL_DATABASE", "borsa")
            )
        except Exception as e:
            print(f"MySQL bağlantı hatası: {e}")
            self.db_conn = None

    def _ensure_tables(self):
        if not self.db_conn:
            return
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol VARCHAR(32) PRIMARY KEY,
                    name VARCHAR(255),
                    sector VARCHAR(255),
                    market_cap BIGINT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prices (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(32),
                    ts DATETIME,
                    open_price DOUBLE,
                    high_price DOUBLE,
                    low_price DOUBLE,
                    close_price DOUBLE,
                    volume DOUBLE,
                    INDEX idx_symbol_ts (symbol, ts)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS live_ticks (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(32),
                    ts DATETIME,
                    price DOUBLE,
                    change_percent DOUBLE,
                    INDEX idx_live_symbol_ts (symbol, ts)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    created_at DATETIME,
                    total_value DOUBLE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_lines (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    snapshot_id BIGINT,
                    symbol VARCHAR(32),
                    lot INT,
                    price DOUBLE,
                    value DOUBLE,
                    INDEX idx_snapshot (snapshot_id)
                )
                """
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Tablo oluşturma hatası: {e}")

    def _upsert_symbol(self, symbol_code, info_dict):
        if not self.db_conn or not info_dict:
            return
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO symbols (symbol, name, sector, market_cap)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    sector = VALUES(sector),
                    market_cap = VALUES(market_cap)
                """,
                (
                    symbol_code,
                    info_dict.get("longName"),
                    info_dict.get("sector"),
                    info_dict.get("marketCap")
                )
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Sembol kaydetme hatası ({symbol_code}): {e}")

    def _save_price_history(self, symbol_code, df):
        if not self.db_conn or df is None or df.empty:
            return
        try:
            records = []
            safe_index = df.index.tz_localize(None) if getattr(df.index, 'tz', None) else df.index
            for ts, row in df.iterrows():
                ts_naive = ts.tz_localize(None) if getattr(ts, 'tzinfo', None) else ts
                records.append(
                    (
                        symbol_code,
                        ts_naive.to_pydatetime() if hasattr(ts_naive, 'to_pydatetime') else ts_naive,
                        float(row.get('Open', None)) if 'Open' in df.columns else None,
                        float(row.get('High', None)) if 'High' in df.columns else None,
                        float(row.get('Low', None)) if 'Low' in df.columns else None,
                        float(row.get('Close', None)) if 'Close' in df.columns else None,
                        float(row.get('Volume', None)) if 'Volume' in df.columns else None,
                    )
                )
            cursor = self.db_conn.cursor()
            cursor.executemany(
                """
                INSERT INTO prices (symbol, ts, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                records
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Fiyat geçmişi kaydetme hatası ({symbol_code}): {e}")

    def _save_live_tick(self, symbol_code, price, change_percent):
        if not self.db_conn:
            return
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO live_ticks (symbol, ts, price, change_percent)
                VALUES (%s, %s, %s, %s)
                """,
                (symbol_code, datetime.now(), float(price) if price is not None else None, float(change_percent) if change_percent is not None else None)
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Canlı tick kaydetme hatası ({symbol_code}): {e}")

    def _save_portfolio_snapshot(self, items):
        if not self.db_conn or not items:
            return
        try:
            total_value = sum(item[4] for item in items)  # value alanı
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT INTO portfolio_snapshots (created_at, total_value) VALUES (%s, %s)",
                (datetime.now(), total_value)
            )
            snapshot_id = cursor.lastrowid
            line_records = []
            for symbol_code, lot, price, value in [(i[0], i[1], i[2], i[4]) for i in items]:
                line_records.append((snapshot_id, symbol_code, lot, price, value))
            cursor.executemany(
                """
                INSERT INTO portfolio_lines (snapshot_id, symbol, lot, price, value)
                VALUES (%s, %s, %s, %s, %s)
                """,
                line_records
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Portföy snapshot kaydetme hatası: {e}")

    def hisse_verisi_cek(self, hisse_kodu, period):
      ticker = yf.Ticker(hisse_kodu)
      data = ticker.history(period=period)
      return data

    def hisse_bilgileri(self, hisse_kodu):
      ticker = yf.Ticker(hisse_kodu)
      info = ticker.info
      # Veritabanına sembol bilgilerini yaz
      try:
          self._upsert_symbol(hisse_kodu, info)
      except Exception:
          pass
      return {
                'isim': info.get("longName"),
                'sektor': info.get("sector"),
                'piyasa_degeri': info.get("marketCap"),
                'fiyat': info.get("regularMarketPrice"),
                'değişim': info.get("regularMarketChangePercent")
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
        # Fiyat geçmişini veritabanına yaz
        try:
            self._save_price_history(hisse_kodu, data)
        except Exception:
            pass
        if data is not None and not data.empty:
            fig=plt.figure(figsize=(12, 6))
            axes=fig.add_axes([0.1,0.1,0.8,0.8])
            axes.plot(data.index, data['Close'], linewidth=2)  #index tarihi verir x için
            axes.set_title(f"{hisse_kodu} Hisse Fiyat Grafiği")
            axes.set_xlabel("Tarih")
            axes.set_ylabel("Fiyat")
            axes.grid(True, alpha=0.3)  #mouse harejketlerine yarar
            axes.tick_params(axis='x', labelrotation=45) #x dekileri 45 derece döndürür okunulabilirlik için
            plt.show()
        else:
            print(f"{hisse_kodu} için veri bulunamadı.")

    def portfoy_analizi(self, hisseler_lotlar):
        print("📈 Portföy Analizi")
        print("-" * 30)

        toplam_deger = 0
        detay_kayitlari = []  # (symbol, lot, price, value)
        for hisse, lot in hisseler_lotlar:
            bilgi = self.hisse_bilgileri(hisse)
            if bilgi:
                deger = bilgi["fiyat"] * lot
                print(f"{hisse}: {bilgi['fiyat']:.2f} TL × {lot} lot = {deger:.2f} TL")
                toplam_deger += deger
                detay_kayitlari.append((hisse, lot, bilgi["fiyat"], deger, deger))
            else:
                print(f"{hisse} için bilgi bulunamadı.")

        print(f"\nToplam Portföy Değeri: {toplam_deger:.2f} TL")
        # Snapshot kaydet
        try:
            self._save_portfolio_snapshot(detay_kayitlari)
        except Exception:
            pass

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

                # Tick verisini kaydet
                try:
                    self._save_live_tick(hisse_kodu, fiyat, değişim)
                except Exception:
                    pass
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
