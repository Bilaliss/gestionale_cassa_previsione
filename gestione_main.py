import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
import random
import json
import os
import io
import re # Importa re qui
from matplotlib import dates as mdates  # Aggiungi questo import


# Importazioni per elaborazione fatture (se disponibili)
try:
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF
    invoice_libs_available = True
except ImportError:
    invoice_libs_available = False
    print("Attenzione: Librerie per elaborazione fatture (pytesseract, Pillow, PyMuPDF) non trovate. Funzionalità disabilitata.")

# Importazioni per previsioni (se disponibili)
try:
    import requests
    from prophet import Prophet
    sales_libs_available = True
except ImportError:
    sales_libs_available = False
    print("Attenzione: Librerie per previsioni (requests, prophet) non trovate. Funzionalità disabilitata.")

# --- Classe per Elaborazione Fatture ---
class InvoiceProcessor:
    def __init__(self, main_app=None):  # Aggiungi questo parametro
        if not invoice_libs_available:
            print("InvoiceProcessor non può funzionare senza le librerie necessarie.")
            return
        self.main_app = main_app  # Memorizza il riferimento all'app principale

        # Configura il percorso di Tesseract per macOS
        try:
            pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
            pytesseract.get_tesseract_version()
        except Exception as e:
            messagebox.showerror("Errore Tesseract",
                                 f"Tesseract non configurato correttamente:\n{str(e)}\n"
                                 "Assicurati di averlo installato con 'brew install tesseract tesseract-lang'")
            print(f"Errore configurazione Tesseract: {e}")

    def update_inventory_from_invoice(self, invoice_text: str):
        """Aggiorna l'inventario in base ai prodotti trovati nella fattura"""
        if not invoice_libs_available:
            return False

        try:
            # Estrai prodotti dalla fattura (esempio semplice)
            products = self.extract_products_from_text(invoice_text)

            for product in products:
                # Cerca se il prodotto esiste già nel menu
                found = False
                for item in self.menu:
                    if item['name'].lower() == product['name'].lower():
                        item['stock'] += product['quantity']
                        found = True
                        break

                if not found:
                    # Aggiungi nuovo prodotto all'inventario
                    new_id = max((item['id'] for item in self.menu), default=0) + 1
                    self.menu.append({
                        'id': new_id,
                        'name': product['name'],
                        'category': 'Fornitura',  # o altra categoria appropriata
                        'price': 0.0,  # da impostare manualmente
                        'cost': product.get('unit_price', 0.0),
                        'stock': product['quantity']
                    })

            self.save_data()  # Salva le modifiche
            return True

        except Exception as e:
            print(f"Errore aggiornamento inventario: {e}")
            return False

    def extract_products_from_text(self, text: str) -> list:
        """Estrai prodotti dalla fattura (da personalizzare in base al formato delle tue fatture)"""
        products = []
        lines = text.split('\n')

        # Esempio di riconoscimento prodotti (da adattare)
        for line in lines:
            # Cerca pattern tipo: "10 x Pomodori San Marzano kg 1,50€"
            match = re.search(r'(\d+)\s*x\s*([a-zA-Z\s]+)\s*(?:kg|lt|pz)?\s*[\d,.]+\s*€?', line, re.IGNORECASE)
            if match:
                products.append({
                    'name': match.group(2).strip(),
                    'quantity': int(match.group(1)),
                    'unit_price': float(match.group(3).replace(',', '.')) if match.group(3) else 0.0
                })

        return products

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Estrai testo da un PDF"""
        if not invoice_libs_available: return "Errore: Librerie PDF mancanti."
        text = ""
        try:
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
        except Exception as e:
            messagebox.showerror("Errore PDF", f"Impossibile leggere il PDF: {e}")
            print(f"Errore nell'estrazione testo PDF: {e}")
        return text

    def extract_text_from_image(self, image_path: str) -> str:
        """Estrai testo da un'immagine usando OCR"""
        if not invoice_libs_available: return "Errore: Librerie OCR mancanti."
        try:
            img = Image.open(image_path)
            # Potrebbe essere necessario specificare la lingua esplicitamente
            text = pytesseract.image_to_string(img, lang='ita+eng') # Aggiungi lingue se necessario
            return text
        except pytesseract.TesseractNotFoundError:
             messagebox.showerror("Errore Tesseract", "Tesseract non trovato o non configurato correttamente.")
             print("Errore OCR: Tesseract non trovato.")
             return "Errore: Tesseract non trovato."
        except Exception as e:
            messagebox.showerror("Errore OCR", f"Errore durante l'OCR: {e}")
            print(f"Errore nell'OCR: {e}")
            return ""

    def process_invoice(self, file_path: str) -> dict:
        """Elabora una fattura e aggiorna l'inventario"""
        invoice_data = {
            'supplier': 'N/D',
            'amount': 0.0,
            'date': 'N/D',
            'raw_text': '',
            'inventory_updated': False
        }

        if not invoice_libs_available:
            return invoice_data

        text = ""
        file_lower = file_path.lower()

        if file_lower.endswith('.pdf'):
            text = self.extract_text_from_pdf(file_path)
        elif file_lower.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
            text = self.extract_text_from_image(file_path)
        else:
            messagebox.showerror("Formato non supportato", "Seleziona un file PDF o immagine.")
            return invoice_data

        if not text:
            return invoice_data

        invoice_data.update({
            'supplier': self.extract_supplier(text),
            'amount': self.extract_amount(text),
            'date': self.extract_date(text),
            'raw_text': text
        })

        # Aggiorna l'inventario con i prodotti della fattura
        invoice_data['inventory_updated'] = self.update_inventory_from_invoice(text)

        return invoice_data

    def extract_supplier(self, text: str) -> str:
        """Estrai il nome del fornitore (esempio molto semplificato)"""
        # Cerca keyword comuni o pattern (es. Spett.le, Ragione Sociale, Ditta)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # Esempio: cerca una linea non vuota dopo una keyword
             if ("spett.le" in line.lower() or "ditta" in line.lower()) and i + 1 < len(lines):
                 potential_supplier = lines[i+1].strip()
                 if potential_supplier: return potential_supplier
             # Esempio: Cerca righe in maiuscolo vicino all'inizio
             if i < 5 and line.isupper() and len(line.split()) > 1:
                 return line.strip()
        # Fallback
        if len(lines) > 1: return lines[1].strip() # Ipotesi molto debole
        return "Sconosciuto"

    def extract_amount(self, text: str) -> float:
        """Estrai l'importo totale (esempio migliorato con ricerca 'Totale')"""
        # Cerca "Totale Fattura", "Importo Totale", "Total Amount" ecc. seguito da un numero
        # Pattern: (parole chiave) + opzionale(:) + opzionale(€/EUR) + numero con . o ,
        # (?i) per case-insensitive
        pattern = r'(?i)(?:totale|importo|ammontare|total)\s*(?:fattura|invoice|amount|due)?\s*:?\s*(?:€|EUR)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})|\d+[.,]\d{1,2})'
        matches = re.findall(pattern, text)

        if matches:
            # Prendi l'ultimo match, spesso il totale finale
            amount_str = matches[-1].replace('.', '').replace(',', '.') # Normalizza a 'xxx.yy'
            try:
                return float(amount_str)
            except ValueError:
                pass # Prova il prossimo pattern

        # Fallback: cerca l'importo più alto preceduto da € o alla fine di una riga
        pattern_fallback = r'(?:€|EUR)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})|\d+[.,]\d{1,2})\s*(?:€|EUR)?$' # Fine riga o con simbolo
        matches_fallback = re.findall(pattern_fallback, text, re.MULTILINE)
        if matches_fallback:
            amounts = []
            for m in matches_fallback:
                try:
                    amounts.append(float(m.replace('.', '').replace(',', '.')))
                except ValueError:
                    continue
            if amounts:
                return max(amounts) # Spesso il totale è l'importo più alto

        return 0.0

    def extract_date(self, text: str) -> str:
        """Estrai la data della fattura (esempio migliorato)"""
        # Cerca pattern comuni: dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy, yyyy-mm-dd
        # Priorità a date vicine a "Data Fattura", "Date"
        pattern = r'(?i)(?:data|date)\s*(?:fattura|invoice)?\s*:?\s*(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}[./-]\d{2}[./-]\d{2})'
        matches = re.findall(pattern, text)
        if matches:
            return matches[0] # Prende la prima data associata a una keyword

        # Fallback: cerca qualsiasi data nel formato comune
        pattern_fallback = r'(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}[./-]\d{2}[./-]\d{2})'
        matches_fallback = re.findall(pattern_fallback, text)
        if matches_fallback:
            # Potrebbe restituire la data più recente trovata o la prima
            return matches_fallback[0] # Restituisce la prima trovata

        return "Data non trovata"

# --- Classe per Previsioni Vendite ---
class SalesPredictor:
    def __init__(self, weather_api_key: str, event_api_key: str = None):
        if not sales_libs_available:
            print("SalesPredictor non può funzionare senza le librerie necessarie.")
            self.model = None
            return
        self.weather_api_key = weather_api_key
        self.event_api_key = event_api_key # Non usato nell'esempio base
        self.model = None

    def get_weather_data(self, location: str, start_date_str: str, end_date_str: str) -> list:
        """Ottieni dati meteo storici e futuri da WeatherAPI per un range di date."""
        if not sales_libs_available or not self.weather_api_key: return []
        base_url = "http://api.weatherapi.com/v1/history.json" # Per dati storici
        forecast_url = "http://api.weatherapi.com/v1/forecast.json" # Per previsioni future

        all_weather_data = []
        current_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        today = datetime.now().date()

        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            if current_date.date() < today:
                 # Dati Storici
                 api_url = f"{base_url}?key={self.weather_api_key}&q={location}&dt={date_str}"
            elif current_date.date() == today:
                 # Dati di Oggi (dal forecast, prendendo il primo giorno)
                 api_url = f"{forecast_url}?key={self.weather_api_key}&q={location}&days=1" # Prende oggi
            else:
                 # Dati Futuri (massimo 14 giorni da oggi con piano free)
                 days_ahead = (current_date.date() - today).days + 1 # +1 per includere oggi
                 if days_ahead > 14: # Limite API (adjust based on your plan)
                     print(f"Warning: WeatherAPI free plan forecast limited to 14 days. Skipping {date_str}")
                     current_date += timedelta(days=1)
                     continue
                 # Chiediamo previsione per 'days_ahead' giorni e prendiamo quella giusta
                 api_url = f"{forecast_url}?key={self.weather_api_key}&q={location}&days={days_ahead}"

            try:
                response = requests.get(api_url, timeout=10) # Aggiunto timeout
                response.raise_for_status() # Solleva eccezione per errori HTTP
                data = response.json()

                if 'forecast' in data and 'forecastday' in data['forecast']:
                    # Trova il giorno corretto nel forecast
                    day_data = next((day for day in data['forecast']['forecastday'] if day['date'] == date_str), None)
                    if day_data:
                         all_weather_data.append(day_data)

            except requests.exceptions.RequestException as e:
                print(f"Errore nel recupero dati meteo per {date_str}: {e}")
                # Aggiungi un placeholder o gestisci l'errore come preferisci
                all_weather_data.append({'date': date_str, 'day': {'avgtemp_c': None, 'totalprecip_mm': None}})
            except Exception as e:
                 print(f"Errore generico meteo per {date_str}: {e}")
                 all_weather_data.append({'date': date_str, 'day': {'avgtemp_c': None, 'totalprecip_mm': None}})

            current_date += timedelta(days=1)

        return all_weather_data

    def get_local_events(self, location: str, start_date: datetime, end_date: datetime) -> list:
        """Ottieni eventi locali (Placeholder - da implementare con API reale)"""
        print(f"Ricerca eventi (placeholder) per {location} da {start_date.date()} a {end_date.date()}")
        # Esempio: Implementazione reale userebbe un'API come Ticketmaster, Eventbrite, o dati locali.
        # Qui restituiamo una lista vuota o eventi fittizi per dimostrazione.
        # Formato: [{'date': 'YYYY-MM-DD', 'name': 'Nome Evento', 'attendance_factor': 1.5}, ...]
        # attendance_factor potrebbe essere un moltiplicatore o un valore fisso da aggiungere
        return []

    def prepare_data_for_prophet(self, sales_data: list[dict], weather_data: list[dict], events_data: list[dict]) -> pd.DataFrame:
        """Prepara i dati nel formato richiesto da Prophet (ds, y, regressori)."""
        if not sales_libs_available: return pd.DataFrame()

        if not sales_data:
            print("Nessun dato di vendita fornito per la preparazione.")
            return pd.DataFrame()

        df = pd.DataFrame(sales_data)
        if 'date' not in df.columns or 'sales' not in df.columns:
             raise ValueError("I dati di vendita devono contenere le colonne 'date' e 'sales'")

        df['ds'] = pd.to_datetime(df['date'])
        df = df.rename(columns={'sales': 'y'})
        df = df.sort_values('ds') # Assicura ordine cronologico

        # Mappa meteo per data
        weather_map = {pd.to_datetime(day['date']): day['day'] for day in weather_data if 'date' in day and 'day' in day}

        # Mappa eventi per data
        event_map = {}
        for event in events_data:
            date = pd.to_datetime(event['date'])
            # Qui potresti definire come l'evento influisce (es. valore binario, fattore, etc.)
            event_map[date] = event.get('attendance_factor', 1) # Default: 1 (nessun evento) o 0

        # Aggiungi regressori
        df['temp'] = df['ds'].map(lambda d: weather_map.get(d, {}).get('avgtemp_c'))
        df['rain'] = df['ds'].map(lambda d: weather_map.get(d, {}).get('totalprecip_mm'))
        df['event'] = df['ds'].map(lambda d: event_map.get(d, 0)) # Default a 0 se nessun evento

        # Gestione valori mancanti (importante per Prophet)
        # Opzione 1: Forward fill (riempie con l'ultimo valore valido)
        df['temp'] = df['temp'].ffill().bfill() # Forward fill e poi back fill per inizio/fine
        df['rain'] = df['rain'].ffill().bfill()
        df['event'] = df['event'].fillna(0) # Assume 0 per eventi mancanti

        # Opzione 2: Riempire con media o valore fisso (meno comune per serie temporali)
        # df['temp'] = df['temp'].fillna(df['temp'].mean())
        # df['rain'] = df['rain'].fillna(0) # Assume 0 pioggia se mancante

        # Rimuovi righe dove y è NaN (non si può addestrare senza target)
        df = df.dropna(subset=['y'])

        # Mantieni solo le colonne necessarie per Prophet
        return df[['ds', 'y', 'temp', 'rain', 'event']]

    def train_model(self, training_data: pd.DataFrame):
        """Addestra il modello Prophet."""
        if not sales_libs_available: return None
        if training_data.empty:
             print("Dati di addestramento vuoti, impossibile addestrare.")
             return None

        self.model = Prophet(
            # yearly_seasonality=True, # Puoi configurare stagionalità
            # weekly_seasonality=True,
            # daily_seasonality=False # Solitamente non utile per vendite giornaliere aggregate
        )

        # Aggiungi regressori solo se esistono e non sono costanti (o quasi)
        if 'temp' in training_data.columns and training_data['temp'].nunique() > 1:
            self.model.add_regressor('temp')
        else: print("Regressore 'temp' non aggiunto (mancante o costante).")

        if 'rain' in training_data.columns and training_data['rain'].nunique() > 1:
             self.model.add_regressor('rain')
        else: print("Regressore 'rain' non aggiunto (mancante o costante).")

        if 'event' in training_data.columns and training_data['event'].nunique() > 1:
             self.model.add_regressor('event')
        else: print("Regressore 'event' non aggiunto (mancante o costante).")

        try:
            # --- CORREZIONE QUI ---
            # Converti le chiavi dei regressori in una lista prima della concatenazione
            regressor_list = list(self.model.extra_regressors.keys())
            columns_for_fit = ['ds', 'y'] + regressor_list
            self.model.fit(training_data[columns_for_fit])
            # --- FINE CORREZIONE ---

            print("Modello Prophet addestrato.")
            return self.model
        except Exception as e:
            messagebox.showerror("Errore Addestramento", f"Errore durante l'addestramento del modello:\n{e}")
            print(f"Errore fit Prophet: {e}")
            self.model = None
            return None

    def make_predictions(self, days_to_predict: int, latest_date: datetime, location: str) -> pd.DataFrame | None:
        """Prepara i dati futuri e fa previsioni."""
        if not sales_libs_available or not self.model:
            messagebox.showerror("Errore Previsione", "Modello non addestrato o librerie mancanti.")
            return None

        # Crea dataframe futuro
        future_df = self.model.make_future_dataframe(periods=days_to_predict)

        # Date per cui recuperare meteo ed eventi futuri
        start_future_date = latest_date + timedelta(days=1)
        end_future_date = future_df['ds'].max()

        # Ottieni meteo ed eventi per il periodo futuro
        print(f"Recupero dati futuri da {start_future_date.strftime('%Y-%m-%d')} a {end_future_date.strftime('%Y-%m-%d')}")
        future_weather = self.get_weather_data(location, start_future_date.strftime('%Y-%m-%d'), end_future_date.strftime('%Y-%m-%d'))
        future_events = self.get_local_events(location, start_future_date, end_future_date)

        # Mappa meteo ed eventi futuri per data
        weather_map = {pd.to_datetime(day['date']): day['day'] for day in future_weather if 'date' in day and 'day' in day}
        event_map = {pd.to_datetime(evt['date']): evt.get('attendance_factor', 1) for evt in future_events}

        # Aggiungi regressori al dataframe futuro
        # Solo se il regressore è stato effettivamente aggiunto al modello
        if 'temp' in self.model.extra_regressors:
            future_df['temp'] = future_df['ds'].map(lambda d: weather_map.get(d, {}).get('avgtemp_c'))
            # Gestisci NaN nel futuro (es. riempi con l'ultimo valore storico o una media)
            last_known_temp = self.model.history['temp'].iloc[-1] if not self.model.history.empty and 'temp' in self.model.history.columns else 15 # Valore di fallback
            future_df['temp'] = future_df['temp'].ffill().fillna(last_known_temp)

        if 'rain' in self.model.extra_regressors:
            future_df['rain'] = future_df['ds'].map(lambda d: weather_map.get(d, {}).get('totalprecip_mm'))
            last_known_rain = self.model.history['rain'].iloc[-1] if not self.model.history.empty and 'rain' in self.model.history.columns else 0
            future_df['rain'] = future_df['rain'].ffill().fillna(last_known_rain)

        if 'event' in self.model.extra_regressors:
             future_df['event'] = future_df['ds'].map(lambda d: event_map.get(d, 0)) # Assume 0 se non c'è evento
             future_df['event'] = future_df['event'].fillna(0)

        # Rimuovi colonne non usate come regressori prima di predict
        cols_to_keep = ['ds'] + list(self.model.extra_regressors.keys())
        future_df_predict = future_df[cols_to_keep]

        # Fai previsioni
        try:
            forecast = self.model.predict(future_df_predict)
            print("Previsioni generate.")
             # Restituisci solo le previsioni future (escludi i dati storici inclusi da make_future_dataframe)
            return forecast[forecast['ds'] > pd.to_datetime(latest_date)][['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        except Exception as e:
            messagebox.showerror("Errore Previsione", f"Errore durante la generazione delle previsioni:\n{e}")
            print(f"Errore predict Prophet: {e}")
            return None

    def predict_sales_pipeline(self, location: str, historical_sales: list[dict], days_to_predict: int = 7) -> pd.DataFrame | None:
        """Pipeline completa: dati -> prepara -> addestra -> prevedi."""
        if not sales_libs_available: return None

        if not historical_sales:
             messagebox.showerror("Dati Insufficienti", "Nessun dato storico di vendita fornito per l'addestramento.")
             return None

        # 1. Determina il range di date necessario (storico + futuro)
        df_hist = pd.DataFrame(historical_sales)
        df_hist['date'] = pd.to_datetime(df_hist['date'])
        start_date = df_hist['date'].min()
        latest_date = df_hist['date'].max()
        end_date_forecast = latest_date + timedelta(days=days_to_predict)

        # 2. Ottieni dati meteo per l'intero periodo
        print(f"Recupero dati meteo da {start_date.strftime('%Y-%m-%d')} a {end_date_forecast.strftime('%Y-%m-%d')}")
        all_weather_data = self.get_weather_data(location, start_date.strftime('%Y-%m-%d'), end_date_forecast.strftime('%Y-%m-%d'))

        # 3. Ottieni dati eventi per l'intero periodo (storico + futuro)
        print("Recupero dati eventi (placeholder)...")
        all_events_data = self.get_local_events(location, start_date, end_date_forecast)

        # 4. Prepara dati di addestramento (solo periodo storico)
        print("Preparazione dati di addestramento...")
        training_data = self.prepare_data_for_prophet(historical_sales, all_weather_data, all_events_data)

        if training_data is None or training_data.empty:
             messagebox.showerror("Errore Dati", "Fallimento nella preparazione dei dati di addestramento.")
             return None

        # 5. Addestra il modello
        print("Addestramento modello...")
        if not self.train_model(training_data):
            # Errore già mostrato da train_model
            return None

        # 6. Fai previsioni
        print("Generazione previsioni...")
        forecast = self.make_predictions(days_to_predict, latest_date, location)

        return forecast


# --- Classe Principale dell'Applicazione GUI ---
class RestaurantManagementSystem:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gestionale Ristorante - Professional Edition v2")
        self.root.geometry("1300x850") # Leggermente più grande
        self.root.configure(bg="#f0f0f0") # Sfondo leggermente diverso
        self.product_updates = []

        # Carica configurazione (es. API Key)
        self.config = self.load_config()

        # Inizializza dati (prova a caricare da file, altrimenti usa sample)
        self.data_file = "restaurant_data.json"
        self.reservations = []
        self.menu = []
        self.transactions = []
        self.load_data() # Carica dati o crea sample se non esiste il file

        # Stile moderno (leggermente aggiustato)
        self.style = ttk.Style()
        self.style.theme_use("clam") # Prova anche "alt", "default"
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 10)) # Font più moderno
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6, background="#e0e0e0", relief=tk.FLAT)
        self.style.map("TButton", background=[('active', '#c5c5c5')])
        self.style.configure("TNotebook", background="#f0f0f0", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[12, 6], background="#d0d0d0", foreground="#333")
        self.style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#000")])
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#d0d0d0", relief=tk.FLAT)
        self.style.map("Treeview.Heading", background=[('active', '#c0c0c0')])

        # Inizializza processori esterni (ora che la config è caricata)
        self.invoice_processor = InvoiceProcessor(self) if invoice_libs_available else None
        self.sales_predictor = SalesPredictor(weather_api_key=self.config.get("WEATHER_API_KEY")) if sales_libs_available else None

        # Creazione dell'interfaccia
        self.create_main_frame()
        self.create_menu_bar() # Rinominato da create_menu

        # Salva i dati all'uscita
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def process_invoice_file(self):
        """Elabora il file fattura e mostra la verifica manuale"""
        if not hasattr(self, 'invoice_processor') or not self.invoice_processor:
            messagebox.showerror("Errore", "Modulo di elaborazione fatture non disponibile")
            return

        file_path = filedialog.askopenfilename(
            title="Seleziona Fattura PDF o Immagine",
            filetypes=[("File Fattura", "*.pdf *.png *.jpg *.jpeg *.tiff")]
        )

        if not file_path:
            return

        self.invoice_status_label.config(text="Elaborazione in corso...", foreground='black')
        self.root.update()

        try:
            invoice_data = self.invoice_processor.process_invoice(file_path)

            # Aggiorna l'interfaccia con i dati della fattura
            self.invoice_supplier_label.config(text=invoice_data.get('supplier', 'N/D'))
            self.invoice_date_label.config(text=invoice_data.get('date', 'N/D'))
            self.invoice_amount_label.config(text=f"€ {invoice_data.get('amount', 0.0):.2f}")
            self.invoice_text.delete(1.0, tk.END)
            self.invoice_text.insert(tk.END, invoice_data.get('raw_text', 'Nessun testo estratto.'))

            # Estrai prodotti e mostra la finestra di conferma
            if hasattr(self.invoice_processor, 'extract_products_from_text'):
                products = self.invoice_processor.extract_products_from_text(invoice_data['raw_text'])
                if products:
                    self.show_inventory_update_confirmation(products, invoice_data)
                    self.invoice_status_label.config(text="Fattura elaborata - Verifica i prodotti", foreground='blue')
                else:
                    self.invoice_status_label.config(text="Nessun prodotto rilevato nella fattura", foreground='orange')
            else:
                self.invoice_status_label.config(text="Fattura elaborata (aggiornamento manuale inventario richiesto)",
                                                 foreground='blue')

        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante l'elaborazione: {str(e)}")
            self.invoice_status_label.config(text="Errore durante l'elaborazione", foreground='red')

    def load_config(self) -> dict:
        """Carica configurazione da config.json (crealo se non esiste)"""
        config_file = "config.json"
        default_config = {"WEATHER_API_KEY": "LA_TUA_API_KEY_QUI"}
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    print(f"Caricamento configurazione da {config_file}")
                    return json.load(f)
            else:
                print(f"File di configurazione {config_file} non trovato. Creazione con valori predefiniti.")
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=4)
                messagebox.showinfo("Configurazione", f"Creato file '{config_file}'. Inserisci la tua WeatherAPI Key.")
                return default_config
        except Exception as e:
            messagebox.showerror("Errore Config", f"Impossibile leggere/creare {config_file}: {e}")
            return default_config

    def load_data(self):
        """Carica dati da un file JSON o usa dati di esempio."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.reservations = data.get("reservations", [])
                    self.menu = data.get("menu", [])
                    self.transactions = data.get("transactions", [])
                    print(f"Dati caricati da {self.data_file}")
            else:
                print("File dati non trovato. Caricamento dati di esempio.")
                self.load_sample_data()
                # Salva i dati di esempio per la prossima volta
                self.save_data()
        except Exception as e:
            messagebox.showerror("Errore Caricamento Dati", f"Impossibile caricare i dati: {e}\nVerranno usati dati di esempio.")
            self.load_sample_data()

    def save_data(self):
        """Salva i dati correnti in un file JSON."""
        data = {
            "reservations": self.reservations,
            "menu": self.menu,
            "transactions": self.transactions
        }
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
            # print(f"Dati salvati in {self.data_file}") # Opzionale: log di salvataggio
        except Exception as e:
            messagebox.showerror("Errore Salvataggio Dati", f"Impossibile salvare i dati: {e}")

    def on_closing(self):
        """Chiamato quando la finestra viene chiusa."""
        if messagebox.askokcancel("Uscita", "Salvare le modifiche prima di uscire?"):
            self.save_data()
            print("Dati salvati.")
        self.root.destroy()

    def load_sample_data(self):
        """Genera dati di esempio se il file non esiste"""
        # Prenotazioni
        self.reservations = []
        for i in range(1, 21):
            day = random.randint(1, 28) # Mantiene i giorni validi per tutti i mesi
            month = random.randint(1, 12)
            year = datetime.now().year # Usa l'anno corrente
            try:
                date_obj = datetime(year, month, day)
                date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError: # Gestisce date non valide (es. 31 Feb)
                 date_obj = datetime(year, month, random.randint(1,28))
                 date_str = date_obj.strftime('%Y-%m-%d')

            self.reservations.append({
                "id": i, "name": f"Cliente {random.randint(100, 999)}", "date": date_str,
                "time": f"{random.randint(12, 21)}:{random.choice(['00', '15', '30', '45'])}",
                "table": random.randint(1, 15), "people": random.randint(1, 6),
                "status": random.choice(["Confermata", "In attesa", "Completata", "Cancellata"])
            })
        # Ordina per ID per coerenza
        self.reservations.sort(key=lambda x: x['id'])

        # Menu
        self.menu = [
            {"id": 1, "name": "Pizza Margherita", "category": "Pizze", "price": 8.50, "cost": 3.20, "stock": 50},
            {"id": 2, "name": "Spaghetti Carbonara", "category": "Primi", "price": 12.00, "cost": 4.50, "stock": 30},
            {"id": 3, "name": "Tagliata di Manzo", "category": "Secondi", "price": 18.00, "cost": 8.00, "stock": 20},
            {"id": 4, "name": "Insalata Mista", "category": "Antipasti", "price": 7.00, "cost": 2.50, "stock": 40},
            {"id": 5, "name": "Tiramisù", "category": "Dessert", "price": 6.00, "cost": 2.00, "stock": 40},
            {"id": 6, "name": "Acqua Naturale 1L", "category": "Bevande", "price": 2.50, "cost": 0.50, "stock": 100},
            {"id": 7, "name": "Vino Rosso della Casa 0.5L", "category": "Bevande", "price": 8.00, "cost": 3.00, "stock": 25},
        ]
        self.menu.sort(key=lambda x: x['id'])

        # Transazioni finanziarie
        self.transactions = []
        start_trans_date = datetime.now() - timedelta(days=90) # Ultime 90 giorni
        for i in range(1, 151): # Più transazioni
            trans_date = start_trans_date + timedelta(days=random.randint(0, 89))
            trans_type = random.choice(["Entrata", "Uscita"])
            category = ""
            amount = 0.0
            if trans_type == "Entrata":
                category = random.choice(["Vendite Sala", "Vendite Asporto", "Altro Incasso"])
                amount = round(random.uniform(50, 800), 2)
            else: # Uscita
                category = random.choice(["Fornitori Cibo", "Fornitori Bevande", "Stipendi", "Utenze", "Marketing", "Manutenzione", "Altro Costo"])
                amount = round(random.uniform(20, 500), 2)

            self.transactions.append({
                "id": i, "date": trans_date.strftime('%Y-%m-%d'), "type": trans_type,
                "amount": amount, "category": category, "description": f"Transazione {i} - {category}"
            })
        self.transactions.sort(key=lambda x: (x['date'], x['id'])) # Ordina per data e ID

    def create_main_frame(self):
        """Crea il frame principale con notebook per i vari moduli"""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook per i vari moduli
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Aggiungi schede (ora include tutte quelle definite)
        self.create_dashboard_tab()       # Prima scheda
        self.create_reservation_tab()
        self.create_menu_tab()
        self.create_finance_tab()
        self.create_reports_tab()         # Scheda vuota
        if invoice_libs_available:
            self.create_invoice_tab()     # Aggiunta scheda fatture
        if sales_libs_available:
            self.create_forecast_tab()    # Aggiunta scheda previsioni

    def create_menu_bar(self): # Rinominato
        """Crea la barra dei menu"""
        menubar = tk.Menu(self.root)

        # Menu File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Salva Dati", command=self.save_data)
        file_menu.add_command(label="Esporta Dati (CSV)...", command=self.export_data_dialog) # Modificato per dialogo
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.on_closing) # Usa la funzione di chiusura
        menubar.add_cascade(label="File", menu=file_menu)

        # Menu Modifica (opzionale, per futuro cut/copy/paste)
        # edit_menu = tk.Menu(menubar, tearoff=0)
        # edit_menu.add_command(label="...")
        # menubar.add_cascade(label="Modifica", menu=edit_menu)

        # Menu Aiuto
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Informazioni", command=self.show_about)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

        self.root.config(menu=menubar)

    # --- Metodi helper generici ---
    def create_treeview_with_scrollbar(self, parent, columns: tuple, column_config: dict) -> ttk.Treeview:
        """Crea una Treeview con scrollbar e colonne configurate."""
        frame = ttk.Frame(parent) # Frame per contenere treeview e scrollbar
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")

        # Configura colonne
        for col, conf in column_config.items():
            tree.heading(col, text=conf.get("text", col.capitalize()), anchor=conf.get("anchor", tk.W))
            tree.column(col, width=conf.get("width", 100), anchor=conf.get("anchor", tk.W), stretch=conf.get("stretch", True))

        # Scrollbar verticale
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        return tree

    def clear_treeview(self, tree: ttk.Treeview):
        """Rimuove tutti gli elementi da una Treeview."""
        for item in tree.get_children():
            tree.delete(item)

    # --- Scheda Dashboard (Nuova) ---
    def create_dashboard_tab(self):
        """Crea la scheda Dashboard con riepiloghi."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📊 Dashboard")

        # Layout a griglia per KPi
        kpi_frame = ttk.Frame(tab)
        kpi_frame.pack(fill=tk.X, pady=10)
        kpi_frame.columnconfigure((0, 1, 2, 3), weight=1) # 4 colonne

        # Esempio KPI: Prenotazioni Oggi
        today_str = datetime.now().strftime('%Y-%m-%d')
        reservations_today = sum(1 for r in self.reservations if r['date'] == today_str and r['status'] in ['Confermata', 'In attesa'])
        self.kpi_reservations_label = self.create_kpi_widget(kpi_frame, "Prenotazioni Oggi", f"{reservations_today}", 0)

        # Esempio KPI: Coperti Previsti Oggi
        people_today = sum(r['people'] for r in self.reservations if r['date'] == today_str and r['status'] in ['Confermata', 'In attesa'])
        self.kpi_people_label = self.create_kpi_widget(kpi_frame, "Coperti Previsti Oggi", f"{people_today}", 1)

        # Esempio KPI: Incasso Ieri (approssimativo da transazioni)
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        revenue_yesterday = sum(t['amount'] for t in self.transactions if t['date'] == yesterday_str and t['type'] == 'Entrata')
        self.kpi_revenue_label = self.create_kpi_widget(kpi_frame, "Incasso Ieri", f"€{revenue_yesterday:.2f}", 2)

        # Esempio KPI: Piatti con poca scorta
        low_stock_items = sum(1 for item in self.menu if item.get('stock', 0) < 10) # Soglia esempio: 10
        self.kpi_low_stock_label = self.create_kpi_widget(kpi_frame, "Prodotti Scarsi", f"{low_stock_items}", 3)

        # Grafici principali (es. vendite ultime settimane, categorie menu)
        charts_frame = ttk.Frame(tab)
        charts_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)
        charts_frame.rowconfigure(0, weight=1)

        self.dashboard_sales_chart_frame = ttk.Frame(charts_frame)
        self.dashboard_sales_chart_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        ttk.Label(self.dashboard_sales_chart_frame, text="Vendite Recenti (Placeholder)", font=("Segoe UI", 11, "bold")).pack(pady=5)
        # Qui andrà il grafico vendite

        self.dashboard_menu_chart_frame = ttk.Frame(charts_frame)
        self.dashboard_menu_chart_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        ttk.Label(self.dashboard_menu_chart_frame, text="Categorie Menu (Placeholder)", font=("Segoe UI", 11, "bold")).pack(pady=5)
        # Qui andrà il grafico menu

        # Aggiorna i grafici (chiamata iniziale)
        self.update_dashboard_charts()

    def create_kpi_widget(self, parent, title: str, value: str, grid_col: int) -> ttk.Label:
        """Crea un widget stile KPI"""
        frame = ttk.Frame(parent, borderwidth=1, relief=tk.SOLID, padding=10)
        frame.grid(row=0, column=grid_col, padx=10, sticky=tk.EW)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=title, font=("Segoe UI", 9, "bold"), anchor=tk.CENTER).grid(row=0, column=0, sticky=tk.EW)
        value_label = ttk.Label(frame, text=value, font=("Segoe UI", 16, "bold"), foreground="#3498db", anchor=tk.CENTER)
        value_label.grid(row=1, column=0, sticky=tk.EW, pady=(5,0))
        return value_label # Restituisce l'etichetta del valore per poterla aggiornare

    def update_dashboard_data(self):
        """Aggiorna i valori dei KPI nella Dashboard."""
        # Riaalcola i valori
        today_str = datetime.now().strftime('%Y-%m-%d')
        reservations_today = sum(1 for r in self.reservations if r['date'] == today_str and r['status'] in ['Confermata', 'In attesa'])
        people_today = sum(r['people'] for r in self.reservations if r['date'] == today_str and r['status'] in ['Confermata', 'In attesa'])
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        revenue_yesterday = sum(t['amount'] for t in self.transactions if t['date'] == yesterday_str and t['type'] == 'Entrata')
        low_stock_items = sum(1 for item in self.menu if item.get('stock', 0) < 10)

        # Aggiorna le label
        self.kpi_reservations_label.config(text=f"{reservations_today}")
        self.kpi_people_label.config(text=f"{people_today}")
        self.kpi_revenue_label.config(text=f"€{revenue_yesterday:.2f}")
        self.kpi_low_stock_label.config(text=f"{low_stock_items}")

        # Aggiorna i grafici
        self.update_dashboard_charts()

    def update_dashboard_charts(self):
        """Aggiorna i grafici nella dashboard"""
        # --- Grafico Vendite Recenti ---
        for widget in self.dashboard_sales_chart_frame.winfo_children():
             if isinstance(widget, tk.Canvas): # Rimuovi solo il canvas precedente
                 widget.destroy()

        # Prepara dati (ultimi 30 giorni di entrate)
        sales_recent = [t for t in self.transactions if t['type'] == 'Entrata' and \
                        (datetime.now() - datetime.strptime(t['date'], '%Y-%m-%d')).days <= 30]
        sales_by_date = pd.DataFrame(sales_recent).groupby('date')['amount'].sum().reset_index()
        sales_by_date['date'] = pd.to_datetime(sales_by_date['date'])
        sales_by_date = sales_by_date.sort_values('date')

        if not sales_by_date.empty:
            fig, ax = plt.subplots(figsize=(6, 3.5), dpi=90) # Dimensioni adatte per la grid
            ax.bar(sales_by_date['date'], sales_by_date['amount'], color="#2ecc71")
            ax.set_title("Incassi Ultimi 30 Giorni", fontsize=10)
            ax.set_ylabel("€", fontsize=9)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
            ax.grid(True, linestyle='--', alpha=0.6, axis='y')
            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=self.dashboard_sales_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        else:
             ttk.Label(self.dashboard_sales_chart_frame, text="Nessun dato di vendita recente.").pack()


        # --- Grafico Categorie Menu ---
        for widget in self.dashboard_menu_chart_frame.winfo_children():
            if isinstance(widget, tk.Canvas): widget.destroy()

        categories = pd.DataFrame(self.menu)['category'].value_counts()

        if not categories.empty:
            fig, ax = plt.subplots(figsize=(6, 3.5), dpi=90)
            ax.pie(categories.values, labels=categories.index, autopct='%1.1f%%', startangle=90,
                   colors=plt.cm.Paired.colors, textprops={'fontsize': 9}) # Colori e dimensione testo
            ax.set_title("Distribuzione Piatti per Categoria", fontsize=10)
            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=self.dashboard_menu_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        else:
             ttk.Label(self.dashboard_menu_chart_frame, text="Nessun dato menu disponibile.").pack()

    # --- Scheda Prenotazioni (Rifattorizzata) ---
    def create_reservation_tab(self):
        """Crea la scheda per la gestione delle prenotazioni"""
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="🗓️ Prenotazioni") # Emoji cambiata

        # Frame superiore con controlli
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Filtra per data (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(0, 2))
        self.reservation_date_entry = ttk.Entry(control_frame, width=12)
        self.reservation_date_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.reservation_date_entry.insert(0, datetime.today().strftime('%Y-%m-%d'))
        # Pulsante per cancellare filtro
        ttk.Button(control_frame, text="Mostra Tutti", command=lambda: self.update_reservation_table(clear_filter=True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Filtra", command=self.filter_reservations).pack(side=tk.LEFT, padx=5)
        # Pulsanti azioni a destra
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="Nuova...", command=self.add_or_edit_reservation).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Modifica...", command=lambda: self.add_or_edit_reservation(edit_mode=True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Elimina", command=self.delete_reservation).pack(side=tk.LEFT, padx=5)

        # Tabella prenotazioni (usa helper)
        columns = ("id", "name", "date", "time", "table", "people", "status")
        column_config = {
            "id": {"text": "ID", "width": 50, "anchor": tk.CENTER},
            "name": {"text": "Nome Cliente", "width": 180},
            "date": {"text": "Data", "width": 100, "anchor": tk.CENTER},
            "time": {"text": "Ora", "width": 80, "anchor": tk.CENTER},
            "table": {"text": "Tavolo", "width": 60, "anchor": tk.CENTER},
            "people": {"text": "Persone", "width": 60, "anchor": tk.CENTER},
            "status": {"text": "Stato", "width": 100, "anchor": tk.CENTER}
        }
        self.reservation_tree = self.create_treeview_with_scrollbar(tab, columns, column_config)
        # Evento doppio click per modificare
        self.reservation_tree.bind("<Double-1>", lambda event: self.add_or_edit_reservation(edit_mode=True))

        # Popola la tabella
        self.update_reservation_table()

        # Grafico affluenza (opzionale, potrebbe stare nel dashboard o report)
        # self.create_reservation_chart(tab)

    def update_reservation_table(self, date_filter=None, clear_filter=False):
        """Aggiorna la tabella delle prenotazioni, gestendo il filtro."""
        self.clear_treeview(self.reservation_tree)

        if clear_filter:
            self.reservation_date_entry.delete(0, tk.END) # Pulisci campo data
            current_filter = None
        else:
            current_filter = date_filter if date_filter else self.reservation_date_entry.get()
            # Valida formato data (opzionale ma utile)
            try:
                if current_filter: datetime.strptime(current_filter, '%Y-%m-%d')
            except ValueError:
                 messagebox.showwarning("Formato Data", "Formato data non valido. Usa YYYY-MM-DD.")
                 current_filter = None # Ignora filtro se non valido
                 self.reservation_date_entry.delete(0, tk.END)


        for res in sorted(self.reservations, key=lambda x: (x['date'], x['time'])): # Ordina per data/ora
            if current_filter and res["date"] != current_filter:
                continue

            # Aggiungi tag per colorare righe basate sullo stato (opzionale)
            status_tags = ()
            if res["status"] == "Cancellata": status_tags = ('cancelled',)
            elif res["status"] == "Completata": status_tags = ('completed',)

            self.reservation_tree.insert("", tk.END, values=(
                res.get("id", ""), res.get("name", ""), res.get("date", ""), res.get("time", ""),
                res.get("table", ""), res.get("people", ""), res.get("status", "")
            ), tags=status_tags)

        # Configura i tag di stile
        self.reservation_tree.tag_configure('cancelled', foreground='gray', font=('Segoe UI', 10, 'overstrike'))
        self.reservation_tree.tag_configure('completed', foreground='dark green')

    def filter_reservations(self):
        """Filtra le prenotazioni per data inserita."""
        self.update_reservation_table()

    def add_or_edit_reservation(self, edit_mode=False):
        """Apre un dialogo per aggiungere o modificare una prenotazione."""
        selected_item = None
        initial_data = {}

        if edit_mode:
            selected = self.reservation_tree.selection()
            if not selected:
                messagebox.showwarning("Selezione Mancante", "Seleziona una prenotazione da modificare.")
                return
            selected_item = selected[0]
            res_id = self.reservation_tree.item(selected_item)["values"][0]
            # Trova i dati originali
            try:
                 initial_data = next(r for r in self.reservations if r["id"] == res_id)
            except StopIteration:
                 messagebox.showerror("Errore", f"Prenotazione ID {res_id} non trovata nei dati.")
                 return

        # Crea dialogo Toplevel
        dialog = tk.Toplevel(self.root)
        dialog.title("Nuova Prenotazione" if not edit_mode else f"Modifica Prenotazione ID: {initial_data.get('id', '')}")
        dialog.geometry("450x350") # Un po' più grande
        dialog.resizable(False, False)
        dialog.grab_set() # Blocca interazione con finestra principale

        # Layout a griglia nel dialogo
        dialog.columnconfigure(1, weight=1)

        fields = {
            "name": {"label": "Nome Cliente:", "widget": ttk.Entry, "row": 0},
            "date": {"label": "Data (YYYY-MM-DD):", "widget": ttk.Entry, "row": 1},
            "time": {"label": "Ora (HH:MM):", "widget": ttk.Entry, "row": 2},
            "table": {"label": "Tavolo:", "widget": ttk.Entry, "row": 3},
            "people": {"label": "Persone:", "widget": ttk.Entry, "row": 4},
            "status": {"label": "Stato:", "widget": ttk.Combobox, "row": 5, "values": ["Confermata", "In attesa", "Completata", "Cancellata"]}
        }

        entries = {}
        for key, config in fields.items():
            ttk.Label(dialog, text=config["label"]).grid(row=config["row"], column=0, padx=10, pady=5, sticky=tk.W)
            if config["widget"] == ttk.Combobox:
                widget = ttk.Combobox(dialog, values=config["values"], state="readonly") # Readonly per forzare selezione
                widget.set(initial_data.get(key, config["values"][0])) # Default o valore esistente
            else:
                widget = config["widget"](dialog)
                widget.insert(0, str(initial_data.get(key, ""))) # Inserisci valore esistente o stringa vuota

            # Imposta valori predefiniti per nuova prenotazione
            if not edit_mode:
                 if key == "date": widget.insert(0, datetime.today().strftime('%Y-%m-%d'))
                 if key == "time": widget.insert(0, "19:30")
                 if key == "status": widget.set("Confermata")

            widget.grid(row=config["row"], column=1, padx=10, pady=5, sticky=tk.EW)
            entries[key] = widget

        def validate_and_save():
            data = {}
            try:
                data["name"] = entries["name"].get().strip()
                if not data["name"]: raise ValueError("Il nome cliente è obbligatorio.")

                data["date"] = entries["date"].get().strip()
                datetime.strptime(data["date"], '%Y-%m-%d') # Valida formato data

                data["time"] = entries["time"].get().strip()
                datetime.strptime(data["time"], '%H:%M') # Valida formato ora

                # Valida tavolo e persone come numeri interi > 0
                table_str = entries["table"].get().strip()
                data["table"] = int(table_str) if table_str else None # Permetti tavolo non assegnato?
                if data["table"] is not None and data["table"] <= 0: raise ValueError("Il numero del tavolo deve essere positivo.")

                people_str = entries["people"].get().strip()
                data["people"] = int(people_str) if people_str else 0
                if data["people"] <= 0: raise ValueError("Il numero di persone deve essere almeno 1.")

                data["status"] = entries["status"].get()

            except ValueError as ve:
                messagebox.showerror("Errore Input", str(ve), parent=dialog)
                return
            except Exception as ex:
                 messagebox.showerror("Errore Input", f"Errore nei dati inseriti: {ex}", parent=dialog)
                 return

            # Logica di salvataggio
            if edit_mode:
                # Aggiorna l'elemento esistente nella lista
                res_id = initial_data["id"]
                for i, r in enumerate(self.reservations):
                    if r["id"] == res_id:
                        # Mantieni l'ID originale
                        data["id"] = res_id
                        self.reservations[i] = data
                        break
            else:
                # Aggiungi nuovo elemento con nuovo ID
                new_id = max((r["id"] for r in self.reservations), default=0) + 1
                data["id"] = new_id
                self.reservations.append(data)

            self.update_reservation_table() # Aggiorna tabella principale
            self.update_dashboard_data() # Aggiorna anche la dashboard
            # self.save_data() # Salva subito? O solo alla chiusura? Meglio solo alla chiusura.
            dialog.destroy()

        # Pulsanti Salva/Annulla
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=15, sticky=tk.E)
        ttk.Button(button_frame, text="Salva", command=validate_and_save).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Annulla", command=dialog.destroy).pack(side=tk.LEFT)

    def delete_reservation(self):
        """Elimina la prenotazione selezionata."""
        selected = self.reservation_tree.selection()
        if not selected:
            messagebox.showwarning("Selezione Mancante", "Seleziona una prenotazione da eliminare.")
            return

        item = self.reservation_tree.item(selected[0])
        res_id = item["values"][0]

        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare la prenotazione ID {res_id}?"):
            initial_len = len(self.reservations)
            self.reservations = [r for r in self.reservations if r.get("id") != res_id]
            if len(self.reservations) < initial_len:
                self.update_reservation_table()
                self.update_dashboard_data()
                print(f"Prenotazione ID {res_id} eliminata.")
                # self.save_data() # Salva?
            else:
                messagebox.showerror("Errore", f"Impossibile trovare la prenotazione ID {res_id} da eliminare.")

    # --- Scheda Menu (Rifattorizzata) ---
    def create_menu_tab(self):
        """Crea la scheda per la gestione del menu"""
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="🍽️ Menu")

        # Controlli
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        # Pulsanti azioni a destra
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="Nuovo...", command=self.add_or_edit_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Modifica...", command=lambda: self.add_or_edit_menu_item(edit_mode=True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Elimina", command=self.delete_menu_item).pack(side=tk.LEFT, padx=5)

        # Tabella menu (usa helper)
        columns = ("id", "name", "category", "price", "cost", "margin_pct", "stock")
        column_config = {
            "id": {"text": "ID", "width": 50, "anchor": tk.CENTER},
            "name": {"text": "Nome Piatto", "width": 250},
            "category": {"text": "Categoria", "width": 120},
            "price": {"text": "Prezzo", "width": 80, "anchor": tk.E},
            "cost": {"text": "Costo", "width": 80, "anchor": tk.E},
            "margin_pct": {"text": "Margine %", "width": 90, "anchor": tk.E},
            "stock": {"text": "Giacenza", "width": 80, "anchor": tk.CENTER}
        }
        self.menu_tree = self.create_treeview_with_scrollbar(tab, columns, column_config)
        self.menu_tree.bind("<Double-1>", lambda event: self.add_or_edit_menu_item(edit_mode=True))


        # Popola la tabella
        self.update_menu_table()

        # Grafico (opzionale, meglio in dashboard/report)
        # self.create_menu_chart(tab)

    def update_menu_table(self):
        """Aggiorna la tabella del menu"""
        self.clear_treeview(self.menu_tree)
        categories = sorted(list(set(item.get("category", "Altro") for item in self.menu))) # Ottieni categorie uniche

        for item in sorted(self.menu, key=lambda x: (x.get('category', ''), x.get('name', ''))): # Ordina per categoria e nome
            price = item.get("price", 0.0)
            cost = item.get("cost", 0.0)
            margin = price - cost
            margin_pct = (margin / price * 100) if price > 0 else 0
            stock = item.get("stock", 0) # Gestisce chiave mancante

             # Tag per scorte basse
            stock_tags = ('lowstock',) if stock < 10 else () # Soglia 10

            self.menu_tree.insert("", tk.END, values=(
                item.get("id", ""), item.get("name", ""), item.get("category", ""),
                f"€{price:.2f}", f"€{cost:.2f}", f"{margin_pct:.1f}%", stock
            ), tags=stock_tags)

        self.menu_tree.tag_configure('lowstock', foreground='red', font=('Segoe UI', 10, 'bold'))

    def add_or_edit_menu_item(self, edit_mode=False):
        """Apre dialogo per aggiungere/modificare un piatto."""
        selected_item = None
        initial_data = {}
        title = "Nuovo Piatto / Bevanda"

        if edit_mode:
            selected = self.menu_tree.selection()
            if not selected:
                messagebox.showwarning("Selezione Mancante", "Seleziona un elemento dal menu da modificare.")
                return
            selected_item = selected[0]
            item_id = self.menu_tree.item(selected_item)["values"][0]
            try:
                initial_data = next(m for m in self.menu if m["id"] == item_id)
                title = f"Modifica: {initial_data.get('name', '')}"
            except StopIteration:
                messagebox.showerror("Errore", f"Elemento menu ID {item_id} non trovato.")
                return

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        fields = {
            "name": {"label": "Nome:", "widget": ttk.Entry, "row": 0},
            "category": {"label": "Categoria:", "widget": ttk.Combobox, "row": 1, "values": sorted(list(set(m.get("category","") for m in self.menu if m.get("category")))) + ["Nuova Categoria..."]}, # Aggiunge opzione per nuova categoria
            "price": {"label": "Prezzo Vendita (€):", "widget": ttk.Entry, "row": 2},
            "cost": {"label": "Costo Acquisto/Produz. (€):", "widget": ttk.Entry, "row": 3},
            "stock": {"label": "Giacenza Iniziale:", "widget": ttk.Entry, "row": 4} # O quantità attuale?
        }

        entries = {}
        for key, config in fields.items():
            ttk.Label(dialog, text=config["label"]).grid(row=config["row"], column=0, padx=10, pady=5, sticky=tk.W)
            if config["widget"] == ttk.Combobox:
                widget = ttk.Combobox(dialog, values=config["values"]) # Permette inserimento
                widget.set(initial_data.get(key, config["values"][0] if config["values"] else ""))
                widget.bind("<<ComboboxSelected>>", lambda e, w=widget: self.handle_new_category(w))
                widget.bind("<FocusOut>", lambda e, w=widget: self.handle_new_category(w)) # Anche quando si lascia il campo
            else:
                widget = config["widget"](dialog)
                # Formatta numeri per visualizzazione, ma salva come float/int
                value = initial_data.get(key, "")
                if key in ["price", "cost"] and isinstance(value, (int, float)):
                     widget.insert(0, f"{value:.2f}")
                else:
                     widget.insert(0, str(value))

            widget.grid(row=config["row"], column=1, padx=10, pady=5, sticky=tk.EW)
            entries[key] = widget

        def validate_and_save_menu():
            data = {}
            try:
                data["name"] = entries["name"].get().strip()
                if not data["name"]: raise ValueError("Il nome è obbligatorio.")

                category_val = entries["category"].get().strip()
                if not category_val or category_val == "Nuova Categoria...": raise ValueError("La categoria è obbligatoria.")
                data["category"] = category_val

                # Convalida e converte prezzo, costo, giacenza
                price_str = entries["price"].get().strip().replace(',', '.')
                data["price"] = float(price_str) if price_str else 0.0
                if data["price"] < 0: raise ValueError("Il prezzo non può essere negativo.")

                cost_str = entries["cost"].get().strip().replace(',', '.')
                data["cost"] = float(cost_str) if cost_str else 0.0
                if data["cost"] < 0: raise ValueError("Il costo non può essere negativo.")

                stock_str = entries["stock"].get().strip()
                data["stock"] = int(stock_str) if stock_str else 0
                if data["stock"] < 0: raise ValueError("La giacenza non può essere negativa.")

            except ValueError as ve:
                messagebox.showerror("Errore Input", str(ve), parent=dialog)
                return
            except Exception as ex:
                 messagebox.showerror("Errore Input", f"Errore nei dati inseriti: {ex}", parent=dialog)
                 return

            # Logica di salvataggio
            if edit_mode:
                item_id = initial_data["id"]
                for i, m in enumerate(self.menu):
                    if m["id"] == item_id:
                        data["id"] = item_id
                        self.menu[i] = data
                        break
            else:
                new_id = max((m["id"] for m in self.menu), default=0) + 1
                data["id"] = new_id
                self.menu.append(data)

            self.update_menu_table()
            self.update_dashboard_data() # Aggiorna dashboard (es. categorie, scorte)
            # self.save_data()
            dialog.destroy()

        # Pulsanti
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=15, sticky=tk.E)
        ttk.Button(button_frame, text="Salva", command=validate_and_save_menu).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Annulla", command=dialog.destroy).pack(side=tk.LEFT)

    def handle_new_category(self, combobox_widget):
         """Gestisce l'opzione 'Nuova Categoria...' nel combobox."""
         if combobox_widget.get() == "Nuova Categoria...":
              # Svuota il campo per permettere all'utente di scrivere
              combobox_widget.set("")

    def delete_menu_item(self):
        """Elimina l'elemento selezionato dal menu."""
        selected = self.menu_tree.selection()
        if not selected:
            messagebox.showwarning("Selezione Mancante", "Seleziona un elemento da eliminare.")
            return

        item = self.menu_tree.item(selected[0])
        item_id = item["values"][0]
        item_name = item["values"][1]

        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare '{item_name}' (ID: {item_id}) dal menu?"):
            initial_len = len(self.menu)
            self.menu = [m for m in self.menu if m.get("id") != item_id]
            if len(self.menu) < initial_len:
                self.update_menu_table()
                self.update_dashboard_data()
                print(f"Elemento menu '{item_name}' (ID: {item_id}) eliminato.")
                # self.save_data()
            else:
                messagebox.showerror("Errore", f"Impossibile trovare l'elemento ID {item_id} da eliminare.")

    # --- Scheda Finanze (Base) ---
    def create_finance_tab(self):
        """Crea la scheda per la gestione finanziaria."""
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="💰 Finanze")

        # Controlli (Filtri, Aggiungi Transazione)
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        # TODO: Aggiungere filtri per data, tipo, categoria
        ttk.Button(control_frame, text="Nuova Transazione...", command=self.add_transaction).pack(side=tk.RIGHT, padx=5)

        # Tabella Transazioni
        columns = ("id", "date", "type", "category", "description", "amount")
        column_config = {
            "id": {"text": "ID", "width": 50, "anchor": tk.CENTER},
            "date": {"text": "Data", "width": 100, "anchor": tk.CENTER},
            "type": {"text": "Tipo", "width": 80, "anchor": tk.CENTER},
            "category": {"text": "Categoria", "width": 150},
            "description": {"text": "Descrizione", "width": 300},
            "amount": {"text": "Importo (€)", "width": 100, "anchor": tk.E}
        }
        self.transaction_tree = self.create_treeview_with_scrollbar(tab, columns, column_config)
        # TODO: Aggiungere binding per modifica/elimina transazione

        # Riepilogo Finanziario (Sotto la tabella)
        summary_frame = ttk.Frame(tab, padding=10)
        summary_frame.pack(fill=tk.X)
        self.finance_summary_label = ttk.Label(summary_frame, text="Calcolo riepilogo...", font=("Segoe UI", 10, "bold"))
        self.finance_summary_label.pack(anchor=tk.W)

        # Popola tabella e calcola riepilogo
        self.update_transaction_table()

    def update_transaction_table(self):
        """Aggiorna la tabella delle transazioni e il riepilogo."""
        self.clear_treeview(self.transaction_tree)
        total_income = 0.0
        total_expense = 0.0

        for tr in sorted(self.transactions, key=lambda x: x['date'], reverse=True): # Ordina per data decrescente
            amount = tr.get("amount", 0.0)
            trans_type = tr.get("type", "")

            # Colora entrata/uscita
            tags = ()
            if trans_type == "Entrata":
                tags = ('income',)
                total_income += amount
            elif trans_type == "Uscita":
                tags = ('expense',)
                total_expense += amount

            self.transaction_tree.insert("", tk.END, values=(
                tr.get("id", ""), tr.get("date", ""), trans_type,
                tr.get("category", ""), tr.get("description", ""), f"{amount:.2f}"
            ), tags=tags)

        self.transaction_tree.tag_configure('income', foreground='green')
        self.transaction_tree.tag_configure('expense', foreground='red')

        # Aggiorna riepilogo
        balance = total_income - total_expense
        summary_text = f"Riepilogo Periodo: Entrate: €{total_income:.2f} | Uscite: €{total_expense:.2f} | Saldo: €{balance:.2f}"
        self.finance_summary_label.config(text=summary_text, foreground='blue' if balance >= 0 else 'red')

    def add_transaction(self):
        """Apre dialogo per aggiungere una nuova transazione."""
        # Simile a add_or_edit_reservation/menu_item, ma per le transazioni
        # ... (Implementazione del dialogo per inserire data, tipo, categoria, descrizione, importo) ...
        messagebox.showinfo("Da Implementare", "Funzionalità 'Nuova Transazione' non ancora implementata.")
        # Dopo aver salvato la nuova transazione:
        # self.update_transaction_table()
        # self.update_dashboard_data()
        # self.save_data()

    # --- Scheda Report (Placeholder) ---
    def create_reports_tab(self):
        """Crea la scheda Report (attualmente vuota)."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📈 Report")
        ttk.Label(tab, text="Sezione Report - Da implementare", font=("Segoe UI", 12, "italic")).pack(pady=50)
        # Qui si potrebbero aggiungere:
        # - Report vendite per periodo/categoria/prodotto
        # - Analisi costi (food cost)
        # - Report prenotazioni (tasso di occupazione, no-show)
        # - Report finanziari (profit & loss)

    # --- Scheda Elaborazione Fatture (Integrata) ---
    def create_invoice_tab(self):
        """Crea la scheda per il riconoscimento fatture (se librerie disponibili)."""
        if not hasattr(self, 'invoice_processor') or not self.invoice_processor:
            return

        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="🧾 Fatture Fornitori")

        # Frame per selezione file
        file_frame = ttk.Frame(tab)
        file_frame.pack(fill=tk.X, pady=5)

        # Verifica che il metodo esista prima di creare il pulsante
        if hasattr(self, 'process_invoice_file'):
            ttk.Button(file_frame, text="Carica Fattura (PDF/Immagine)...",
                       command=self.process_invoice_file).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Label(file_frame, text="Funzionalità non disponibile").pack(side=tk.LEFT)

        self.invoice_status_label = ttk.Label(file_frame, text="")
        self.invoice_status_label.pack(side=tk.LEFT, padx=10)

        # Frame per risultati (dati estratti + testo raw)
        result_frame = ttk.Frame(tab)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        result_frame.columnconfigure(0, weight=1) # Colonna per il testo
        result_frame.rowconfigure(1, weight=1) # Riga per il Text widget

        # Area dati estratti
        data_area = ttk.LabelFrame(result_frame, text="Dati Estratti", padding=10)
        data_area.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        data_area.columnconfigure(1, weight=1)
        data_area.columnconfigure(3, weight=1)

        ttk.Label(data_area, text="Fornitore:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.invoice_supplier_label = ttk.Label(data_area, text="N/D", font=("Segoe UI", 10, "bold"))
        self.invoice_supplier_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(data_area, text="Data:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.invoice_date_label = ttk.Label(data_area, text="N/D", font=("Segoe UI", 10, "bold"))
        self.invoice_date_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(data_area, text="Importo Totale:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.invoice_amount_label = ttk.Label(data_area, text="€ 0.00", font=("Segoe UI", 10, "bold"), foreground="darkblue")
        self.invoice_amount_label.grid(row=1, column=1, sticky=tk.W, padx=5)
        # TODO: Aggiungere pulsante per creare transazione da fattura

        # Area testo estratto
        text_area_frame = ttk.Frame(result_frame)
        text_area_frame.grid(row=1, column=0, sticky="nsew")

        ttk.Label(text_area_frame, text="Testo Rilevato:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0,2))
        self.invoice_text = tk.Text(text_area_frame, wrap=tk.WORD, height=15, borderwidth=1, relief=tk.SOLID, font=("Courier New", 9))
        scrollbar = ttk.Scrollbar(text_area_frame, orient=tk.VERTICAL, command=self.invoice_text.yview)
        self.invoice_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.invoice_text.pack(fill=tk.BOTH, expand=True)

    def create_forecast_tab(self):
        """Crea la scheda per le previsioni di vendita (se librerie disponibili)."""
        if not self.sales_predictor: return

        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="🔮 Previsioni Vendite")

        # Controlli per la configurazione
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Località (es. Roma, IT):").pack(side=tk.LEFT, padx=(0, 2))
        self.location_entry = ttk.Entry(control_frame, width=20)
        self.location_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.location_entry.insert(0, "Parma, IT") # Esempio con nazione

        ttk.Label(control_frame, text="Giorni da Prevedere:").pack(side=tk.LEFT, padx=(0, 2))
        self.forecast_days = ttk.Combobox(control_frame, values=[3, 7, 14], width=5, state="readonly")
        self.forecast_days.pack(side=tk.LEFT, padx=(0, 10))
        self.forecast_days.set(7)

        ttk.Button(control_frame, text="Genera Previsioni", command=self.generate_forecast).pack(side=tk.LEFT, padx=5)
        self.forecast_status_label = ttk.Label(control_frame, text="")
        self.forecast_status_label.pack(side=tk.LEFT, padx=10)

        # Area per visualizzare risultati (testo + grafico)
        result_frame = ttk.Frame(tab)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        result_frame.rowconfigure(1, weight=1) # Riga del grafico espandibile
        result_frame.columnconfigure(0, weight=1)

        # Area testo previsioni
        self.forecast_text_label = ttk.Label(result_frame, text="Previsioni:", font=("Segoe UI", 9, "bold"))
        self.forecast_text_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self.forecast_text = tk.Text(result_frame, wrap=tk.WORD, height=8, borderwidth=1, relief=tk.SOLID, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.forecast_text.yview)
        self.forecast_text.configure(yscrollcommand=scrollbar.set)
        # Usa grid per il text widget e scrollbar
        self.forecast_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 10))

        # Frame per il grafico
        self.forecast_chart_frame = ttk.Frame(result_frame, borderwidth=1, relief=tk.SOLID)
        self.forecast_chart_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        # Label interna per titolo grafico
        self.forecast_chart_title = ttk.Label(self.forecast_chart_frame, text="Grafico Previsioni", font=("Segoe UI", 10, "bold"))
        self.forecast_chart_title.pack(pady=5)

    def show_inventory_update_confirmation(self, products, invoice_data):
        """Mostra una finestra di dialogo per confermare l'aggiornamento inventario"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Conferma Aggiornamento Inventario")
        dialog.geometry("800x600")
        dialog.grab_set()

        # Frame principale
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Sezione informazioni fattura
        info_frame = ttk.LabelFrame(main_frame, text="Dettagli Fattura", padding=10)
        info_frame.pack(fill=tk.X, pady=5)

        ttk.Label(info_frame, text=f"Fornitore: {invoice_data.get('supplier', 'N/D')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Data: {invoice_data.get('date', 'N/D')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Importo: €{invoice_data.get('amount', 0.0):.2f}").pack(anchor=tk.W)

        # Sezione prodotti rilevati
        products_frame = ttk.LabelFrame(main_frame, text="Prodotti Rilevati", padding=10)
        products_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Treeview per i prodotti
        columns = ("name", "quantity", "unit_price", "action")
        tree = ttk.Treeview(products_frame, columns=columns, show="headings")
        tree.heading("name", text="Prodotto")
        tree.heading("quantity", text="Quantità")
        tree.heading("unit_price", text="Prezzo Unitario")
        tree.heading("action", text="Azione")

        tree.column("name", width=250)
        tree.column("quantity", width=100, anchor=tk.CENTER)
        tree.column("unit_price", width=150, anchor=tk.E)
        tree.column("action", width=200, anchor=tk.CENTER)

        # Aggiungi prodotti alla treeview
        self.product_updates = []  # Memorizza le modifiche
        for idx, product in enumerate(products):
            existing_item = next((item for item in self.menu
                                  if item['name'].lower() == product['name'].lower()), None)

            action = "AGGIUNGI" if not existing_item else f"Aggiorna (+{product['quantity']})"

            tree.insert("", tk.END, values=(
                product['name'],
                product['quantity'],
                f"€{product.get('unit_price', 0.0):.2f}",
                action
            ), iid=str(idx))

            # Memorizza i dati originali per riferimento
            self.product_updates.append({
                'original': product,
                'modified': product.copy(),
                'existing': existing_item
            })

        # Aggiungi la possibilità di modificare i valori
        def edit_product(event):
            item = tree.focus()
            if not item:
                return

            idx = int(item)
            product = self.product_updates[idx]['modified']

            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title("Modifica Prodotto")

            ttk.Label(edit_dialog, text="Nome:").grid(row=0, column=0, padx=5, pady=5)
            name_entry = ttk.Entry(edit_dialog)
            name_entry.grid(row=0, column=1, padx=5, pady=5)
            name_entry.insert(0, product['name'])

            ttk.Label(edit_dialog, text="Quantità:").grid(row=1, column=0, padx=5, pady=5)
            qty_entry = ttk.Entry(edit_dialog)
            qty_entry.grid(row=1, column=1, padx=5, pady=5)
            qty_entry.insert(0, str(product['quantity']))

            ttk.Label(edit_dialog, text="Prezzo Unitario:").grid(row=2, column=0, padx=5, pady=5)
            price_entry = ttk.Entry(edit_dialog)
            price_entry.grid(row=2, column=1, padx=5, pady=5)
            price_entry.insert(0, str(product.get('unit_price', 0.0)))

            def save_changes():
                try:
                    self.product_updates[idx]['modified']['name'] = name_entry.get()
                    self.product_updates[idx]['modified']['quantity'] = int(qty_entry.get())
                    self.product_updates[idx]['modified']['unit_price'] = float(price_entry.get().replace(',', '.'))

                    # Aggiorna la visualizzazione
                    existing = self.product_updates[idx]['existing']
                    action = "AGGIUNGI" if not existing else f"Aggiorna (+{qty_entry.get()})"

                    tree.item(item, values=(
                        name_entry.get(),
                        qty_entry.get(),
                        f"€{float(price_entry.get().replace(',', '.')):.2f}",
                        action
                    ))

                    edit_dialog.destroy()
                except ValueError:
                    messagebox.showerror("Errore", "Inserisci valori validi", parent=edit_dialog)

            ttk.Button(edit_dialog, text="Salva", command=save_changes).grid(row=3, columnspan=2, pady=10)

        tree.bind("<Double-1>", edit_product)

        # Scrollbar
        scrollbar = ttk.Scrollbar(products_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Pulsanti di controllo
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        def apply_updates():
            for update in self.product_updates:
                modified = update['modified']
                existing = update['existing']

                if existing:
                    # Aggiorna prodotto esistente
                    existing['stock'] += modified['quantity']
                    if 'cost' in existing:
                        existing['cost'] = modified.get('unit_price', existing['cost'])
                else:
                    # Aggiungi nuovo prodotto
                    new_id = max((item['id'] for item in self.menu), default=0) + 1
                    self.menu.append({
                        'id': new_id,
                        'name': modified['name'],
                        'category': 'Fornitura',
                        'price': 0.0,  # Da impostare manualmente
                        'cost': modified.get('unit_price', 0.0),
                        'stock': modified['quantity']
                    })

            self.save_data()
            self.update_menu_table()
            dialog.destroy()
            messagebox.showinfo("Successo", "Inventario aggiornato con successo!", parent=self.root)

        ttk.Button(button_frame, text="Conferma e Applica", command=apply_updates).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def generate_forecast(self):
        """Genera e visualizza le previsioni di vendita."""
        if not self.sales_predictor: return

        location = self.location_entry.get().strip()
        if not location:
            messagebox.showwarning("Input Mancante", "Inserisci una località.")
            return
        try:
            days = int(self.forecast_days.get())
        except ValueError:
            messagebox.showwarning("Input Non Valido", "Seleziona un numero valido di giorni.")
            return

        self.forecast_status_label.config(text="Generazione previsioni in corso...", foreground='orange')
        self.root.update_idletasks()

        # Prepara dati storici dalle transazioni 'Entrata'
        # Nota: Questo è un esempio semplice. Vendite reali potrebbero essere più complesse da calcolare.
        sales_df = pd.DataFrame([t for t in self.transactions if t.get('type') == 'Entrata'])
        if sales_df.empty:
             messagebox.showerror("Dati Mancanti", "Nessuna transazione di 'Entrata' trovata per generare dati storici.")
             self.forecast_status_label.config(text="Errore: Dati storici mancanti.", foreground='red')
             return

        sales_df['date'] = pd.to_datetime(sales_df['date'])
        # Aggrega vendite per giorno
        historical_sales_agg = sales_df.groupby(sales_df['date'].dt.date)['amount'].sum().reset_index()
        historical_sales_agg.rename(columns={'amount': 'sales'}, inplace=True)
        # Converti in formato lista di dizionari richiesto dalla pipeline
        historical_sales_list = historical_sales_agg.to_dict('records')
        # Converti date object back to string YYYY-MM-DD
        for record in historical_sales_list:
            record['date'] = record['date'].strftime('%Y-%m-%d')


        # Assicurati ci siano abbastanza dati storici (Prophet ne richiede almeno 2, ma molti di più sono raccomandati)
        if len(historical_sales_list) < 10: # Soglia minima arbitraria
            messagebox.showwarning("Dati Insufficienti", f"Sono necessari più dati storici per una previsione affidabile (trovati solo {len(historical_sales_list)} giorni con vendite).")
            # Potresti decidere di non procedere o procedere con cautela
            # return # Scegli se bloccare o meno

        try:
            # Esegui la pipeline di previsione
            forecast_df = self.sales_predictor.predict_sales_pipeline(
                location=location,
                historical_sales=historical_sales_list,
                days_to_predict=days
            )

            # Visualizza risultati
            self.forecast_text.delete(1.0, tk.END)
            if forecast_df is not None and not forecast_df.empty:
                # Formatta output per leggibilità
                forecast_df['ds'] = forecast_df['ds'].dt.strftime('%Y-%m-%d (%a)') # Aggiunge giorno settimana
                forecast_df['yhat'] = forecast_df['yhat'].round(2)
                forecast_df['yhat_lower'] = forecast_df['yhat_lower'].round(2)
                forecast_df['yhat_upper'] = forecast_df['yhat_upper'].round(2)
                forecast_string = forecast_df.to_string(index=False, justify='center',
                                                        col_space=15,
                                                        header=["Data Prev.", "Vendita Prev.", "Min Prev.", "Max Prev."])

                self.forecast_text.insert(tk.END, "--- PREVISIONI DI VENDITA STIMATE ---\n\n")
                self.forecast_text.insert(tk.END, forecast_string)
                self.show_forecast_plot(forecast_df)  # Usa forecast_df invece di forecast                self.forecast_status_label.config(text="Previsioni generate.", foreground='green')
            else:
                self.forecast_text.insert(tk.END, "Nessuna previsione generata o errore durante il processo.")
                self.clear_forecast_plot()
                self.forecast_status_label.config(text="Errore o nessuna previsione.", foreground='red')

        except Exception as e:
             messagebox.showerror("Errore Previsione", f"Errore durante la pipeline di previsione:\n{str(e)}")
             self.forecast_status_label.config(text="Errore.", foreground='red')
             print(f"Errore imprevisto in generate_forecast: {e}") # Log più dettagliato in console
             self.clear_forecast_plot()

    import plotly.graph_objects as go

    def show_forecast_plot(self, forecast):
        """Mostra il grafico delle previsioni con matplotlib"""
        # Usa direttamente le date come datetime
        dates = forecast['ds']

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, forecast['yhat'], label='Previsione', color='#4e79a7')
        ax.fill_between(dates, forecast['yhat_lower'], forecast['yhat_upper'],
                        color='#4e79a7', alpha=0.2, label='Intervallo di confidenza')

        ax.set_title("Previsioni di Vendita")
        ax.set_xlabel("Data")
        ax.set_ylabel("Vendite stimate")
        ax.legend()
        ax.grid(True)

        # Formatta le etichette delle date
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d (%a)'))
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Mostra il grafico nell'interfaccia Tkinter
        self.clear_forecast_plot()
        canvas = FigureCanvasTkAgg(fig, master=self.forecast_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Aggiungi toolbar di navigazione (opzionale)
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar = NavigationToolbar2Tk(canvas, self.forecast_chart_frame)
        toolbar.update()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def clear_forecast_plot(self):
        """Rimuove il grafico precedente (FigureCanvasTkAgg) dal frame e chiude la figura Matplotlib."""
        widget_to_destroy = None
        figure_to_close = None

        for widget in self.forecast_chart_frame.winfo_children():
            # Trova il widget FigureCanvasTkAgg
            if isinstance(widget, FigureCanvasTkAgg):
                widget_to_destroy = widget
                figure_to_close = widget.figure  # Salva la figura associata
                # Non uscire subito dal loop, potresti avere label di errore da rimuovere
            # Rimuovi eventuali label di errore precedenti (non il titolo principale)
            elif isinstance(widget, ttk.Label) and widget != self.forecast_chart_title:
                widget.destroy()

        # Distruggi il widget Tkinter DOPO aver iterato
        if widget_to_destroy:
            widget_to_destroy.get_tk_widget().destroy()

        # Chiudi la figura Matplotlib per liberare memoria
        if figure_to_close:
            plt.close(figure_to_close)

    # --- Metodi Menu Bar ---
    def export_data_dialog(self):
         """Chiede all'utente cosa esportare e dove."""
         dialog = tk.Toplevel(self.root)
         dialog.title("Esporta Dati in CSV")
         dialog.geometry("350x250")
         dialog.grab_set()

         ttk.Label(dialog, text="Seleziona i dati da esportare:").pack(pady=10)

         export_options = {
              "Prenotazioni": tk.BooleanVar(value=True),
              "Menu": tk.BooleanVar(value=True),
              "Transazioni": tk.BooleanVar(value=True)
         }

         for name, var in export_options.items():
              ttk.Checkbutton(dialog, text=name, variable=var).pack(anchor=tk.W, padx=20)

         def do_export():
              folder_selected = filedialog.askdirectory(title="Seleziona Cartella di Destinazione")
              if not folder_selected:
                   return # Utente ha annullato

              exported_files = []
              try:
                   if export_options["Prenotazioni"].get():
                        df = pd.DataFrame(self.reservations)
                        filepath = os.path.join(folder_selected, "prenotazioni.csv")
                        df.to_csv(filepath, index=False, encoding='utf-8-sig') # utf-8-sig per compatibilità Excel
                        exported_files.append(filepath)

                   if export_options["Menu"].get():
                        df = pd.DataFrame(self.menu)
                        filepath = os.path.join(folder_selected, "menu.csv")
                        df.to_csv(filepath, index=False, encoding='utf-8-sig')
                        exported_files.append(filepath)

                   if export_options["Transazioni"].get():
                        df = pd.DataFrame(self.transactions)
                        filepath = os.path.join(folder_selected, "transazioni.csv")
                        df.to_csv(filepath, index=False, encoding='utf-8-sig')
                        exported_files.append(filepath)

                   if exported_files:
                        messagebox.showinfo("Esportazione Completata",
                                            f"Dati esportati con successo nella cartella:\n{folder_selected}",
                                            parent=dialog)
                        dialog.destroy()
                   else:
                        messagebox.showwarning("Nessuna Selezione", "Nessun dato selezionato per l'esportazione.", parent=dialog)

              except Exception as e:
                   messagebox.showerror("Errore Esportazione", f"Errore durante l'esportazione:\n{e}", parent=dialog)


         ttk.Button(dialog, text="Esporta Selezionati", command=do_export).pack(pady=20)


    def show_about(self):
        """Mostra finestra 'Informazioni su'"""
        about_text = """
        Gestionale Ristorante - Professional Edition v2.0
        (c) 2024-2025 Bilal Ismail / Baladi srl

        Un sistema gestionale per ristoranti con moduli per:
        - Dashboard Riepilogativa
        - Prenotazioni Clienti
        - Gestione Menu e Giacenze
        - Tracciamento Finanziario
        - Elaborazione Fatture (Richiede Tesseract, PyMuPDF, Pillow)
        - Previsioni di Vendita (Richiede Prophet, Requests)

        Sviluppato con Python e Tkinter.
        """
        messagebox.showinfo("Informazioni", about_text)

# --- Avvio dell'Applicazione ---
if __name__ == "__main__":
    root = tk.Tk()
    app = RestaurantManagementSystem(root)
    root.mainloop()
