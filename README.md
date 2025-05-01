# 📈 Penny Stock Trading Competition 🏆

A web application built with Streamlit for hosting a friendly penny stock trading competition. Users can register, simulate buying/selling penny stocks (<= $5.00) with a starting virtual capital ($500), track their portfolio performance, and compete on a leaderboard.

**(Optional: Add a screenshot of the app here)**
## ✨ Features

* **User Authentication:** Secure registration and login using `streamlit-authenticator` and `bcrypt` password hashing.
* **Trade Simulation:** Enter Buy/Sell orders for stock tickers.
* **Penny Stock Focus:** Implicitly designed for stocks trading at $5.00 or less (though not strictly enforced on manual entry yet).
* **Portfolio Tracking:**
    * Calculates cash balance, holdings (shares, average buy price).
    * Tracks realized and unrealized Profit/Loss (P/L).
    * Calculates total portfolio value based on current market prices (via `yfinance`).
* **Dashboard View:**
    * Key performance metrics (Total Value, P/L, Cash).
    * Portfolio value over time chart (with time frame selection).
    * Asset allocation pie chart.
    * Detailed holdings table with current value and unrealized P/L.
    * Trade history log for the user (with delete functionality).
* **Leaderboard:** Ranks participants based on percentage portfolio performance. Includes a chart comparing all participants' portfolio values over time.
* **Admin Panel:**
    * View all registered users.
    * Delete users.
    * View all trades across all users.
    * Delete any specific trade transaction.
* **Data Persistence:** Uses a local SQLite database (`trades.db`) to store user and trade data.

## 🛠️ Tech Stack

* **Framework:** Streamlit
* **Language:** Python
* **Data Handling:** Pandas
* **Database:** SQLite
* **Authentication:** streamlit-authenticator, bcrypt
* **Charting:** Plotly Express
* **Stock Data:** yfinance

## ⚙️ Setup & Running Locally

To run this application on your local machine:

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/RickMoranis/Penny_Stock_Challenge.git](https://github.com/RickMoranis/Penny_Stock_Challenge.git)
    cd Penny_Stock_Challenge
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate it:
    # Windows: .\venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Secrets:** Create a file named `.streamlit/secrets.toml` in the project root directory with your cookie settings:
    ```toml
    # .streamlit/secrets.toml
    [cookie]
    name = "some_descriptive_cookie_name"
    key = "generate_a_random_secret_key_here" # Use a strong random string
    expiry_days = 30
    ```

5.  **Run the App:**
    ```bash
    streamlit run app.py
    ```
    The app should open in your web browser. The `trades.db` file and tables will be created automatically on the first run if they don't exist.

## 🚀 Deployment

This application is intended for deployment on platforms like Streamlit Community Cloud.

**(Optional: Add link to your deployed app once ready)**
Remember to add the content of your `secrets.toml` file to the secrets management section of your deployment platform (do **not** commit `secrets.toml` to Git).

## Usage

1.  Navigate to the app URL (local or deployed).
2.  Register a new account using the 'Register' tab.
3.  Log in using the 'Login' tab.
4.  Use the sidebar to enter new Buy/Sell trades for ticker symbols.
5.  View your performance and holdings on the "My Dashboard" tab.
6.  Check your ranking on the "Leaderboard" tab.
7.  Admins can access the "Admin Panel" to manage users and trades.

## 🔮 Future Work

* Implement CSV upload functionality to allow users to bulk-import trades from brokerage exports, including validation against competition rules (price <= $5, simulated $500 cash flow).
* Implement manual database backup download for Admins.
* Consider migrating to a persistent cloud database for more robust data storage if usage grows.

---

*(Optional: Add License Information here, e.g., MIT License)*