import csv
import io
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SMARTCART_SECRET", "smartcart-demo-secret-change-me")
app.config["DATABASE"] = str(DATABASE)

CATEGORIES = ["Fruits & Vegetables", "Dairy", "Beverages", "Snacks", "Groceries", "Personal Care"]


def get_db():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def query(sql, parameters=(), one=False):
    connection = get_db()
    try:
        cursor = connection.execute(sql, parameters)
        result = cursor.fetchone() if one else cursor.fetchall()
        return result
    finally:
        connection.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def init_db():
    connection = get_db()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Administrator'
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT
        );
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            brand TEXT,
            supplier_id INTEGER,
            purchase_price REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_stock INTEGER NOT NULL DEFAULT 5,
            expiry_date TEXT,
            image_url TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id),
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            user_id INTEGER,
            sale_date TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL DEFAULT 0,
            tax REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Paid',
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER UNIQUE NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_at TEXT NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE
        );
    """)
    if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        connection.execute("INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)",
                           ("admin", generate_password_hash("admin123"), "Admin"))
    for category in CATEGORIES:
        connection.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
    if connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
        suppliers = [
            ("SUP-001", "Fresh Farms", "Fresh Farms Organics", "+91 98765 10001", "hello@freshfarms.in", "Nashik, Maharashtra"),
            ("SUP-002", "Dairy Direct", "Dairy Direct Foods", "+91 98765 10002", "orders@dairydirect.in", "Pune, Maharashtra"),
            ("SUP-003", "Bharat Grocers", "Bharat Grocers Ltd.", "+91 98765 10003", "sales@bharatgrocers.in", "Mumbai, Maharashtra"),
            ("SUP-004", "Daily Brew", "Daily Brew Beverages", "+91 98765 10004", "team@dailybrew.in", "Bengaluru, Karnataka"),
            ("SUP-005", "Carewell", "Carewell Essentials", "+91 98765 10005", "care@carewell.in", "New Delhi"),
        ]
        connection.executemany("INSERT INTO suppliers (supplier_code, name, company, phone, email, address) VALUES (?, ?, ?, ?, ?, ?)", suppliers)
    if connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        customers = [
            ("CUS-001", "Rahul Sharma", "+91 98100 10001", "rahul@example.com", "12 Park Street"),
            ("CUS-002", "Aisha Khan", "+91 98100 10002", "aisha@example.com", "44 Lake View"),
            ("CUS-003", "Vikram Singh", "+91 98100 10003", "vikram@example.com", "8 Green Avenue"),
            ("CUS-004", "Meera Joshi", "+91 98100 10004", "meera@example.com", "19 Sunrise Road"),
            ("CUS-005", "Arjun Patel", "+91 98100 10005", "arjun@example.com", "7 Market Lane"),
        ]
        connection.executemany("INSERT INTO customers (customer_code, name, phone, email, address) VALUES (?, ?, ?, ?, ?)", customers)
    if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        category_ids = {row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM categories")}
        supplier_ids = {row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM suppliers")}
        products = [
            ("PRD-001", "Basmati Rice", "Groceries", "Daawat", "Bharat Grocers", 620, 760, 42, 10, "2027-04-30"),
            ("PRD-002", "Organic Sugar", "Groceries", "Madhur", "Bharat Grocers", 42, 58, 68, 15, "2028-01-15"),
            ("PRD-003", "Full Cream Milk", "Dairy", "Amul", "Dairy Direct", 52, 64, 8, 12, (date.today() + timedelta(days=3)).isoformat()),
            ("PRD-004", "Whole Wheat Bread", "Groceries", "Harvest", "Bharat Grocers", 34, 48, 24, 8, (date.today() + timedelta(days=6)).isoformat()),
            ("PRD-005", "Butter Biscuits", "Snacks", "Parle", "Bharat Grocers", 18, 25, 55, 10, "2027-02-02"),
            ("PRD-006", "Sunflower Cooking Oil", "Groceries", "Fortune", "Bharat Grocers", 128, 156, 5, 10, "2027-08-20"),
            ("PRD-007", "Assam Tea", "Beverages", "Tata", "Daily Brew", 165, 210, 34, 8, "2027-12-20"),
            ("PRD-008", "Instant Coffee", "Beverages", "Bru", "Daily Brew", 220, 275, 29, 8, "2027-10-05"),
            ("PRD-009", "Iodized Salt", "Groceries", "Tata", "Bharat Grocers", 18, 24, 76, 12, "2028-05-14"),
            ("PRD-010", "Wheat Flour", "Groceries", "Aashirvaad", "Bharat Grocers", 44, 62, 38, 10, "2027-05-22"),
            ("PRD-011", "Tomato", "Fruits & Vegetables", "Farm Fresh", "Fresh Farms", 28, 40, 18, 10, (date.today() + timedelta(days=2)).isoformat()),
            ("PRD-012", "Potato", "Fruits & Vegetables", "Farm Fresh", "Fresh Farms", 24, 35, 62, 12, (date.today() + timedelta(days=14)).isoformat()),
            ("PRD-013", "Red Onion", "Fruits & Vegetables", "Farm Fresh", "Fresh Farms", 30, 45, 4, 10, (date.today() + timedelta(days=8)).isoformat()),
            ("PRD-014", "Mango Juice", "Beverages", "Real", "Daily Brew", 78, 105, 27, 8, "2027-03-10"),
            ("PRD-015", "Herbal Bath Soap", "Personal Care", "Dove", "Carewell", 48, 65, 46, 8, "2028-09-01"),
        ]
        for item in products:
            code, name, category, brand, supplier, purchase, selling, quantity, minimum, expiry = item
            cursor = connection.execute("""INSERT INTO products
                (product_code, name, category_id, brand, supplier_id, purchase_price, selling_price, quantity, min_stock, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (code, name, category_ids[category], brand, supplier_ids[supplier], purchase, selling, quantity, minimum, expiry))
            connection.execute("INSERT INTO inventory (product_id, updated_at) VALUES (?, ?)", (cursor.lastrowid, datetime.now().isoformat(timespec="seconds")))
    if connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] < 10:
        demo_products = connection.execute("SELECT id, selling_price FROM products ORDER BY id LIMIT 10").fetchall()
        demo_customers = connection.execute("SELECT id FROM customers ORDER BY id LIMIT 5").fetchall()
        admin_id = connection.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
        for index in range(10):
            product = demo_products[index]
            quantity = 1 + (index % 2)
            subtotal = product["selling_price"] * quantity
            sale_date = (datetime.now() - timedelta(days=index)).isoformat(timespec="seconds")
            invoice = f"DEMO-{index + 1:04d}"
            sale_cursor = connection.execute("""INSERT OR IGNORE INTO sales
                (invoice_number, customer_id, user_id, sale_date, subtotal, discount, tax, total, payment_method)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)""", (invoice, demo_customers[index % len(demo_customers)]["id"], admin_id, sale_date, subtotal, subtotal * 0.05, subtotal * 1.05, ["Cash", "UPI", "Card"][index % 3])).lastrowid
            sale = sale_cursor if sale_cursor and connection.execute("SELECT changes()").fetchone()[0] else None
            if sale:
                connection.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total) VALUES (?, ?, ?, ?, ?)", (sale, product["id"], quantity, product["selling_price"], subtotal))
                connection.execute("INSERT INTO payments (sale_id, method, amount, paid_at) VALUES (?, ?, ?, ?)", (sale, ["Cash", "UPI", "Card"][index % 3], subtotal * 1.05, sale_date))
    connection.commit()
    connection.close()


def product_query(search="", category=""):
    sql = """SELECT p.*, c.name AS category_name, s.name AS supplier_name
             FROM products p JOIN categories c ON p.category_id = c.id
             LEFT JOIN suppliers s ON p.supplier_id = s.id WHERE 1=1"""
    params = []
    if search:
        sql += " AND (p.name LIKE ? OR p.product_code LIKE ? OR p.brand LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if category:
        sql += " AND c.name = ?"
        params.append(category)
    return query(sql + " ORDER BY p.id DESC", params)


@app.context_processor
def inject_globals():
    low_stock_count = 0
    if session.get("user_id"):
        low_stock_count = query("SELECT COUNT(*) AS total FROM products WHERE quantity <= min_stock", one=True)["total"]
    return {"today": date.today().strftime("%d %b %Y"), "app_name": "SmartCart", "low_stock_count": low_stock_count}


@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "products": query("SELECT COUNT(*) AS total FROM products", one=True)["total"],
        "customers": query("SELECT COUNT(*) AS total FROM customers", one=True)["total"],
        "sales": query("SELECT COALESCE(SUM(total), 0) AS total FROM sales WHERE date(sale_date) = date('now', 'localtime')", one=True)["total"],
        "low_stock": query("SELECT COUNT(*) AS total FROM products WHERE quantity <= min_stock", one=True)["total"],
    }
    recent = query("""SELECT s.*, COALESCE(c.name, 'Walk-in Customer') AS customer,
                     COUNT(si.id) AS item_count FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
                     LEFT JOIN sale_items si ON si.sale_id=s.id GROUP BY s.id ORDER BY s.id DESC LIMIT 6""")
    low_stock = query("SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id WHERE p.quantity <= p.min_stock ORDER BY p.quantity ASC LIMIT 5")
    expiry = query("""SELECT p.*, CAST(julianday(p.expiry_date) - julianday('now', 'localtime') AS INTEGER) AS days_left
                     FROM products p WHERE p.expiry_date IS NOT NULL AND date(p.expiry_date) <= date('now', 'localtime', '+30 day') ORDER BY p.expiry_date LIMIT 5""")
    sales_chart = query("SELECT date(sale_date) AS day, COALESCE(SUM(total),0) AS amount FROM sales WHERE date(sale_date) >= date('now','localtime','-6 day') GROUP BY day ORDER BY day")
    category_chart = query("""SELECT c.name, COALESCE(SUM(si.total),0) AS amount FROM sale_items si
                             JOIN products p ON p.id=si.product_id JOIN categories c ON c.id=p.category_id
                             GROUP BY c.id ORDER BY amount DESC""")
    return render_template("dashboard.html", stats=stats, recent=recent, low_stock=low_stock, expiry=expiry, sales_chart=sales_chart, category_chart=category_chart)


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        form = request.form
        try:
            connection = get_db()
            cursor = connection.execute("""INSERT INTO products (product_code,name,category_id,brand,supplier_id,purchase_price,selling_price,quantity,min_stock,expiry_date,image_url)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (form["product_code"], form["name"], form["category_id"], form.get("brand"), form.get("supplier_id") or None, float(form.get("purchase_price", 0)), float(form.get("selling_price", 0)), int(form.get("quantity", 0)), int(form.get("min_stock", 5)), form.get("expiry_date") or None, form.get("image_url")))
            connection.execute("INSERT INTO inventory (product_id, updated_at) VALUES (?, ?)", (cursor.lastrowid, datetime.now().isoformat(timespec="seconds")))
            connection.commit(); connection.close()
            flash("Product added to inventory.", "success")
        except (ValueError, sqlite3.IntegrityError) as error:
            flash(f"Could not add product: {error}", "danger")
        return redirect(url_for("products"))
    return render_template("products.html", products=product_query(request.args.get("q", ""), request.args.get("category", "")), categories=query("SELECT * FROM categories ORDER BY name"), suppliers=query("SELECT * FROM suppliers ORDER BY name"), search=request.args.get("q", ""))


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product: return redirect(url_for("products"))
    if request.method == "POST":
        form = request.form
        connection = get_db()
        connection.execute("""UPDATE products SET product_code=?,name=?,category_id=?,brand=?,supplier_id=?,purchase_price=?,selling_price=?,quantity=?,min_stock=?,expiry_date=?,image_url=? WHERE id=?""", (form["product_code"], form["name"], form["category_id"], form.get("brand"), form.get("supplier_id") or None, float(form.get("purchase_price", 0)), float(form.get("selling_price", 0)), int(form.get("quantity", 0)), int(form.get("min_stock", 5)), form.get("expiry_date") or None, form.get("image_url"), product_id))
        connection.execute("UPDATE inventory SET updated_at=? WHERE product_id=?", (datetime.now().isoformat(timespec="seconds"), product_id)); connection.commit(); connection.close()
        flash("Product updated.", "success"); return redirect(url_for("products"))
    return render_template("product_form.html", product=product, categories=query("SELECT * FROM categories ORDER BY name"), suppliers=query("SELECT * FROM suppliers ORDER BY name"))


@app.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    connection = get_db(); connection.execute("DELETE FROM products WHERE id=?", (product_id,)); connection.commit(); connection.close(); flash("Product removed.", "success"); return redirect(url_for("products"))


@app.route("/inventory")
@login_required
def inventory():
    rows = query("""SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.quantity ASC""")
    return render_template("inventory.html", products=rows)


def simple_entity(table, code_field, title, fields):
    if request.method == "POST":
        form = request.form
        values = [form.get(field, "").strip() for field in fields]
        try:
            connection = get_db(); connection.execute(f"INSERT INTO {table} ({code_field}, {', '.join(fields)}) VALUES ({', '.join(['?'] * (len(fields) + 1))})", [form.get(code_field, "").strip()] + values); connection.commit(); connection.close(); flash(f"{title} added.", "success")
        except sqlite3.IntegrityError: flash(f"That {title.lower()} code already exists.", "danger")
    rows = query(f"SELECT * FROM {table} ORDER BY id DESC")
    return rows


@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    rows = simple_entity("customers", "customer_code", "Customer", ["name", "phone", "email", "address"])
    search = request.args.get("q", ""); rows = [row for row in rows if not search or search.lower() in (row["name"] or "").lower() or search.lower() in (row["phone"] or "").lower()]
    return render_template("customers.html", customers=rows)


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    rows = simple_entity("suppliers", "supplier_code", "Supplier", ["name", "company", "phone", "email", "address"])
    search = request.args.get("q", ""); rows = [row for row in rows if not search or search.lower() in (row["name"] or "").lower() or search.lower() in (row["company"] or "").lower()]
    return render_template("suppliers.html", suppliers=rows)


@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        try:
            items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(items, str): import json; items = json.loads(items)
            items = items or []
            if not items: return jsonify(error="Cart is empty."), 400
            connection = get_db(); subtotal = 0; validated = []
            for item in items:
                product = connection.execute("SELECT * FROM products WHERE id=?", (int(item["id"]),)).fetchone(); quantity = int(item["quantity"])
                if not product or quantity < 1 or product["quantity"] < quantity: raise ValueError(f"Insufficient stock for {item.get('name', 'product')}.")
                line_total = product["selling_price"] * quantity; subtotal += line_total; validated.append((product, quantity, line_total))
            discount = float(payload.get("discount", 0) or 0); tax = max(0, subtotal - discount) * 0.05; total = max(0, subtotal - discount) + tax
            invoice = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{connection.execute('SELECT COUNT(*) FROM sales').fetchone()[0] + 1}"
            customer_id = payload.get("customer_id") or None; payment = payload.get("payment_method", "Cash")
            cursor = connection.execute("INSERT INTO sales (invoice_number,customer_id,user_id,sale_date,subtotal,discount,tax,total,payment_method) VALUES (?,?,?,?,?,?,?,?,?)", (invoice, customer_id, session["user_id"], datetime.now().isoformat(timespec="seconds"), subtotal, discount, tax, total, payment))
            for product, quantity, line_total in validated:
                connection.execute("INSERT INTO sale_items (sale_id,product_id,quantity,unit_price,total) VALUES (?,?,?,?,?)", (cursor.lastrowid, product["id"], quantity, product["selling_price"], line_total)); connection.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (quantity, product["id"]))
            connection.execute("INSERT INTO payments (sale_id,method,amount,paid_at) VALUES (?,?,?,?)", (cursor.lastrowid, payment, total, datetime.now().isoformat(timespec="seconds"))); connection.commit(); connection.close()
            if request.is_json: return jsonify(success=True, invoice=invoice, total=total)
            flash(f"Invoice {invoice} generated successfully.", "success"); return redirect(url_for("sales"))
        except (ValueError, KeyError, sqlite3.Error) as error:
            if request.is_json: return jsonify(error=str(error)), 400
            flash(str(error), "danger")
    return render_template("billing.html", products=query("SELECT * FROM products WHERE quantity > 0 ORDER BY name"), customers=query("SELECT * FROM customers ORDER BY name"))


@app.route("/sales")
@login_required
def sales():
    rows = query("""SELECT s.*, COALESCE(c.name,'Walk-in Customer') AS customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id ORDER BY s.id DESC""")
    summary = query("SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS transactions, COALESCE(AVG(total),0) AS average FROM sales", one=True)
    return render_template("sales.html", sales=rows, summary=summary)


@app.route("/reports")
@login_required
def reports():
    summary = query("""SELECT COALESCE(SUM(s.total),0) revenue, COALESCE(SUM(si.quantity*p.purchase_price),0) cost,
                      COALESCE(SUM(si.total),0)-COALESCE(SUM(si.quantity*p.purchase_price),0) profit
                      FROM sales s JOIN sale_items si ON si.sale_id=s.id JOIN products p ON p.id=si.product_id""", one=True)
    category_data = query("""SELECT c.name, COALESCE(SUM(si.total),0) amount FROM sale_items si JOIN products p ON p.id=si.product_id JOIN categories c ON c.id=p.category_id GROUP BY c.name""")
    return render_template("reports.html", summary=summary, category_data=category_data)


@app.route("/reports/export")
@login_required
def export_report():
    rows = query("SELECT invoice_number,sale_date,total,payment_method,status FROM sales ORDER BY sale_date DESC")
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["Invoice", "Date", "Total", "Payment", "Status"]); writer.writerows([tuple(row) for row in rows])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=smartcart-sales-report.csv"})


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.errorhandler(404)
def not_found(error): return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error): return render_template("500.html"), 500


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
