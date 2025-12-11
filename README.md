# 🛍️ Offline POS (Point-of-Sale) Management System

A robust, locally deployable Point-of-Sale (POS) application built using Python Flask. This system handles sales, inventory control, customer debt tracking, and core business analysis without requiring a constant internet connection.

## 🌟 Project Level

This project is an **Intermediate/Mid-Level Application**. It demonstrates proficiency in database design, secure authentication, complex business logic, and professional deployment practices.

## ⚙️ Technology Stack

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3, Flask | Lightweight web server, routing, and core application logic. |
| **Database** | SQLite, Flask-SQLAlchemy | Local, file-based relational database for data persistence. |
| **Security** | Flask-Login, Werkzeug | Secure session management and password hashing (PBKDF2). |
| **UI/Frontend** | HTML5, CSS3, Jinja2 | Dynamic templating, custom responsive design, and theme switching. |
| **Deployment** | PyInstaller | Used to package the entire application into a single, standalone executable (`.exe`). |

-----

## 🚀 Core Features and Functionality

### 1\. POS Terminal & Checkout

  * **Rapid Product Entry:** Supports adding products via the grid or **QR Code Scanning** (simulated via input).
  * **Dynamic Cart:** Real-time calculation of totals, line item management, and stock validation during checkout.
  * **Flexible Payment:** Supports **Cash, Card, and Credit** (tracking debt for customers).
  * **Receipt Generation:** Creates a printable receipt for every completed transaction.

### 2\. Customer Management & Debt Tracking

  * **Customer CRUD:** Full control over customer profiles (Create, Read, Update, Delete).
  * **Debt Management:** Automatically calculates **Outstanding Credit Balance**.
  * **Payment Recording:** Dedicated functionality to **record payments** and accurately reduce customer debt.
  * **Data Integrity:** Implements **Cascading Deletes** in SQLAlchemy to ensure all related transaction history is removed when a customer profile is deleted.

### 3\. Inventory Control

  * **Product Management:** Tracks name, price, stock, and custom fields (Supplier, Location, Color).
  * **QR Code Integration:** Automatically generates a unique QR code for every product for rapid scanning at the POS.
  * **Bulk Data Handling:** Supports **CSV Import** for quick stock updates and **CSV Export** for reporting.

### 4\. Business Analysis & Reporting

  * **Profit & Loss Metrics:** Calculates **Total Revenue**, **Gross Profit**, and sales breakdown.
  * **Inventory Valuation:** Calculates the **Total Inventory Costing** (estimated investment value of current stock).
  * **Risk Analysis:** Tracks **Total Outstanding Debt** and identifies potential **Dead Stock Candidates**.

-----

## 🛠️ Setup and Installation (For Developers)

Use these instructions to set up the project environment on your local machine.

### Prerequisites

  * Python 3.8+
  * `pip` (Python package installer)

### 1\. Clone the Repository and Set Up Environment

```bash
git clone https://github.com/thelakshaywalia/advance-inventory-manager.git
cd advance-inventory-manager
```

```bash
# Create a virtual environment
python -m venv venv

# Activate the environment
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2\. Install Dependencies

```bash
pip install Flask Flask-SQLAlchemy Flask-Login werkzeug qrcode Pillow
```

### 3\. Run the Application

```bash
# This command creates the database file (database.db) 
# and initializes the default admin user.
python app.py
```

### 4\. Access

Open your web browser and navigate to:

$$\text{[http://127.0.0.1:5000](http://127.0.0.1:5000)}$$

  * **Default Admin Credentials:** `username: admin` | `password: adminpass`

## 📦 Deployment for End-Users

The application can be packaged into a single, runnable `.exe` file using **PyInstaller**, allowing end-users to run the POS system without installing Python.

1.  Ensure all temporary files are cleaned up (`database.db` deleted, `dist/` and `build/` removed).
2.  Use the following command structure to generate the executable:
    ```bash
    pyinstaller app.spec
    ```
3.  The final, deployable executable (`app.exe`) is found in the generated `dist/` folder.

-----

**Developer/Owner:** thelakshaywalia

-----
