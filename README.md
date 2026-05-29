# Breathe ESG Data Ingestion & Review Platform (Prototype)

A high-performance prototype for ingesting, daily calendar pro-rata splitting, normalising, and auditing enterprise activity data (Scope 1/2/3 carbon footprint) from SAP GL exports, Utility bills, and Concur Travel API streams.

---

## 1. Project Directory Structure

```text
breathe-esg-platform/
├── backend/
│   ├── breathe_esg/             # Main Django app settings and root urls
│   ├── ingestion/               # Core calculations, API views, and seed commands
│   │   ├── processors/          # Ingestion engines (sap.py, utility.py, travel.py)
│   │   ├── management/commands/ # seed_data command populating 4 months history
│   │   ├── tests.py             # 100% passing automated test suite
│   │   └── ...
│   ├── requirements.txt         # Django & DRF dependencies
│   ├── db.sqlite3               # Pre-seeded SQLite Database (for local use)
│   ├── Procfile                 # Production WSGI process declaration
│   ├── build.sh                 # Production migration & seeding script
│   └── manage.py                # Django CLI entrypoint
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React dashboard with file-upload, queues & charts
│   │   ├── index.css            # Custom obsidian glassmorphism design tokens
│   │   └── main.jsx             # Entrypoint
│   ├── package.json             # Frontend dependencies
│   ├── vite.config.js           # Vite development proxy setup
│   └── index.html               # Main page layout & SEO
├── render.yaml                  # One-click Render Infrastructure Blueprint
├── MODEL.md                     # Data model schema & justifications
├── DECISIONS.md                 # Technical assumptions, handled subsets & PM questions
├── TRADEOFFS.md                 # Structural tradeoffs log (PDF OCR, OAuth)
└── SOURCES.md                   # Real-world data formats research & production failures
```

---

## 2. One-Click Production Deployment

This project includes a `render.yaml` blueprint. To deploy the entire architecture (Django REST backend, React frontend static site, and fully managed PostgreSQL database):

1. Commit and push the code to your GitHub repository.
2. Go to **Render.com** &rarr; **Blueprints** &rarr; **New Blueprint Instance**.
3. Select your repository.
4. Render will automatically detect the `render.yaml` configuration and provision:
   * **Database**: Managed PostgreSQL instance (`breathe-esg-db`).
   * **Backend**: Django REST web service (`breathe-esg-api`) running under Gunicorn, applying migrations and seeding the database on build.
   * **Frontend**: React static site host (`breathe-esg-dashboard`) built via Vite.
5. Once complete, your frontend dashboard will be live!

---

## 3. Setting Up & Booting the Django Backend Locally

### Prerequisites
* Python 3.12+ or 3.13
* pip & virtualenv

### Boot Instructions
1. Navigate to the `backend/` directory:
   ```powershell
   cd backend
   ```
2. Activate the pre-configured virtual environment:
   ```powershell
   .\venv\Scripts\activate
   ```
3. Apply migrations and seed the database:
   ```powershell
   # Apply database structural migrations
   python manage.py migrate
   
   # Run seeder command
   python manage.py seed_data
   ```
4. Run the Django development server:
   ```powershell
   python manage.py runserver
   ```
   The server will boot and expose APIs at `http://localhost:8000/api/`.

---

## 4. Running the Backend Automated Unit Tests

Our test suite covers pro-rata daily split logic, geocoded flight Haversine distance computations, German header translation, multi-tenant boundaries, and strict auditor reasoning locks.

Run tests using the virtual environment's interpreter:
```powershell
# Inside backend directory
python manage.py test
```

---

## 5. Booting the React Frontend Dashboard Locally

### Prerequisites
* Node.js v20+ or v22+
* npm

### Boot Instructions
1. Navigate to the `frontend/` directory:
   ```powershell
   cd ../frontend
   ```
2. Install packages (if not already completed):
   ```powershell
   npm install
   ```
3. Boot the Vite development hot-reload server:
   ```powershell
   npm run dev
   ```
   Open your browser and navigate to the local server port displayed in the terminal (usually `http://localhost:5173`).

---

## 6. Interactive Review & Ingestion Walkthrough

When you open the React dashboard:
1. **Dashboard Analytics Tab**: Observe dynamic card stats and carbon stack charts. You can use the **Corporate Tenant Switcher** at the bottom-left sidebar to toggle between **Acme Industrial Corp** and **Global Tech Ventures** and verify absolute database multi-tenancy isolation.
2. **Data Ingestion Tab**: 
   * **Drag and Drop / File Upload**: Select your source type (SAP, Utility, or Travel) and drop any valid CSV or JSON file into the dashed uploader. It will parse and normalize it in real-time.
   * **Simulate Feeds**: Click **"Simulate SAP Upload"**, **"Simulate PGE Utility Bill"**, or **"Simulate Travel API"** buttons. These generate and ingest raw client data instantly.
3. **Review Queue Tab**: 
   * Find the row marked **FLAGGED** (SAP Diesel) showing a `Plant JP90 Unresolved` warning.
   * Click **Review** to open the Auditor Drawer. You will see the original raw JSON from SAP showing the unregistered plant `WERKS: JP90`.
   * In the plant field, replace `JP90` with **`DE10`** (Frankfurt plant).
   * Enter an **Audit Justification Reason** in the mandate authorization box (e.g., *"Corrected plant code after invoice manual lookup"*).
   * Click **Save Corrections**.
   * Observe the plant warning clear, status return to standard, and emissions adjust.
4. **Audit Trail Tab**: Open this panel to view your immutable signed action logged, showing previous values, updated values, timestamp, and your specific audit justification.
