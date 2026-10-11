from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
import os
import secrets

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import database_cursor, setup_database

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
LOW_STOCK_LIMIT = 10


@app.before_request
def protect_forms():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    if request.method == "POST":
        submitted = request.form.get("csrf_token", "")
        if not secrets.compare_digest(submitted, session["csrf_token"]):
            abort(400, "Invalid or missing form token. Reload the page and try again.")


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        if session.get("must_change_password") and function.__name__ != "change_password":
            return redirect(url_for("change_password"))
        return function(*args, **kwargs)
    return wrapper


def form_values():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    expiry = request.form.get("expiry", "").strip()
    try:
        price = Decimal(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
        date.fromisoformat(expiry)
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid price, whole-number stock quantity, and expiry date.")
    if not name or not category or not price.is_finite() or price < 0 or stock < 0:
        raise ValueError("Name and category are required; price and stock cannot be negative.")
    return name, category, price, stock, expiry


def fetch_one(query, params=()):
    with database_cursor() as (_, cursor):
        cursor.execute(query, params)
        return cursor.fetchone()


def fetch_all(query, params=()):
    with database_cursor() as (_, cursor):
        cursor.execute(query, params)
        return cursor.fetchall()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = fetch_one("SELECT * FROM users WHERE username = %s", (username,))
        valid = False
        if user:
            try:
                valid = check_password_hash(user["password"], password)
            except (ValueError, TypeError):
                # Upgrade legacy plaintext passwords on a successful login.
                valid = secrets.compare_digest(str(user["password"]), password)
                if valid:
                    with database_cursor(commit=True) as (_, cursor):
                        cursor.execute("UPDATE users SET password=%s WHERE id=%s",
                                       (generate_password_hash(password), user["id"]))
        if valid:
            session.clear()
            session["logged_in"] = True
            session["username"] = user["username"]
            session["must_change_password"] = bool(user["must_change_password"])
            return redirect(url_for("change_password" if user["must_change_password"] else "dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        user = fetch_one("SELECT * FROM users WHERE username = %s", (session["username"],))
        try:
            valid_current = check_password_hash(user["password"], current)
        except (ValueError, TypeError):
            valid_current = bool(user and secrets.compare_digest(str(user["password"]), current))
        if not valid_current:
            flash("Current password is incorrect", "error")
        elif len(new) < 8:
            flash("New password must contain at least 8 characters", "error")
        elif new != confirm:
            flash("Passwords do not match", "error")
        else:
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("UPDATE users SET password=%s, must_change_password=FALSE WHERE id=%s",
                               (generate_password_hash(new), user["id"]))
            session["must_change_password"] = False
            flash("Password changed successfully", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    totals = fetch_one("""
        SELECT COUNT(*) AS total_medicines, COALESCE(SUM(stock), 0) AS total_stock
        FROM medicines
    """)
    low_stock = fetch_one("SELECT COUNT(*) AS n FROM medicines WHERE stock <= %s", (LOW_STOCK_LIMIT,))["n"]
    total_sales = fetch_one("SELECT COALESCE(SUM(total), 0) AS n FROM sales")["n"]
    return render_template("dashboard.html", total_medicines=totals["total_medicines"],
                           total_stock=totals["total_stock"], low_stock=low_stock,
                           total_sales=total_sales)


@app.route("/medicines", methods=["GET", "POST"])
@login_required
def medicines_page():
    if request.method == "POST":
        try:
            values = form_values()
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("""INSERT INTO medicines (name, category, price, stock, expiry)
                                  VALUES (%s, %s, %s, %s, %s)""", values)
            flash("Medicine added successfully", "success")
        except ValueError as error:
            flash(str(error), "error")
        return redirect(url_for("medicines_page"))
    search = request.args.get("search", "").strip()
    medicines = fetch_all("""SELECT id, name, category, price, stock, expiry FROM medicines
                            WHERE name LIKE %s OR category LIKE %s ORDER BY name""",
                          (f"%{search}%", f"%{search}%"))
    return render_template("medicines.html", medicines=medicines)


@app.route("/medicine/edit/<int:medicine_id>", methods=["GET", "POST"])
@login_required
def edit_medicine(medicine_id):
    medicine = fetch_one("SELECT * FROM medicines WHERE id=%s", (medicine_id,))
    if not medicine:
        flash("Medicine not found", "error")
        return redirect(url_for("medicines_page"))
    if request.method == "POST":
        try:
            values = form_values()
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("""UPDATE medicines SET name=%s, category=%s, price=%s, stock=%s,
                                  expiry=%s WHERE id=%s""", (*values, medicine_id))
            flash("Medicine updated successfully", "success")
            return redirect(url_for("medicines_page"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("edit_medicine.html", medicine=medicine)


@app.route("/medicine/delete/<int:medicine_id>", methods=["POST"])
@login_required
def delete_medicine(medicine_id):
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute("DELETE FROM medicines WHERE id=%s", (medicine_id,))
        deleted = cursor.rowcount
    flash("Medicine deleted" if deleted else "Medicine not found", "success" if deleted else "error")
    return redirect(url_for("medicines_page"))


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        address = request.form.get("address", "").strip()
        if not all((name, contact, address)):
            flash("Complete all supplier fields", "error")
        else:
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("INSERT INTO suppliers (name, contact, address) VALUES (%s,%s,%s)",
                               (name, contact, address))
            flash("Supplier added successfully", "success")
        return redirect(url_for("suppliers_page"))
    return render_template("suppliers.html", suppliers=fetch_all("SELECT * FROM suppliers ORDER BY name"))


@app.route("/supplier/edit/<int:supplier_id>", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id):
    supplier = fetch_one("SELECT * FROM suppliers WHERE id=%s", (supplier_id,))
    if not supplier:
        flash("Supplier not found", "error")
        return redirect(url_for("suppliers_page"))
    if request.method == "POST":
        values = tuple(request.form.get(key, "").strip() for key in ("name", "contact", "address"))
        if not all(values):
            flash("Complete all supplier fields", "error")
        else:
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("UPDATE suppliers SET name=%s, contact=%s, address=%s WHERE id=%s",
                               (*values, supplier_id))
            flash("Supplier updated successfully", "success")
            return redirect(url_for("suppliers_page"))
    return render_template("edit_supplier.html", supplier=supplier)


@app.route("/supplier/delete/<int:supplier_id>", methods=["POST"])
@login_required
def delete_supplier(supplier_id):
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute("DELETE FROM suppliers WHERE id=%s", (supplier_id,))
        deleted = cursor.rowcount
    flash("Supplier deleted" if deleted else "Supplier not found", "success" if deleted else "error")
    return redirect(url_for("suppliers_page"))


@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales_page():
    if request.method == "POST":
        try:
            medicine_id = int(request.form.get("medicine_id", ""))
            quantity = int(request.form.get("quantity", ""))
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash("Choose a medicine and enter a quantity greater than zero", "error")
            return redirect(url_for("sales_page"))
        try:
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute("SELECT * FROM medicines WHERE id=%s FOR UPDATE", (medicine_id,))
                medicine = cursor.fetchone()
                if not medicine:
                    raise ValueError("Medicine not found")
                if medicine["expiry"] < date.today():
                    raise ValueError("Expired medicines cannot be sold")
                if quantity > medicine["stock"]:
                    raise ValueError("Insufficient stock")
                total = Decimal(medicine["price"]) * quantity
                cursor.execute("UPDATE medicines SET stock=stock-%s WHERE id=%s", (quantity, medicine_id))
                cursor.execute("""INSERT INTO sales (medicine_id, medicine_name, quantity, price, total)
                                  VALUES (%s,%s,%s,%s,%s)""",
                               (medicine_id, medicine["name"], quantity, medicine["price"], total))
                sale_id = cursor.lastrowid
            flash("Sale recorded and stock updated", "success")
            return redirect(url_for("invoice", sale_id=sale_id))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("sales_page"))
    medicines = fetch_all("SELECT * FROM medicines WHERE stock > 0 ORDER BY name")
    sales = fetch_all("""SELECT id, medicine_name AS medicine, quantity, price, total,
                          DATE_FORMAT(sale_date, '%Y-%m-%d %H:%i') AS date
                          FROM sales ORDER BY sale_date DESC, id DESC""")
    return render_template("sales.html", medicines=medicines, sales=sales)


@app.route("/invoice/<int:sale_id>")
@login_required
def invoice(sale_id):
    sale = fetch_one("""SELECT id, medicine_name AS medicine, quantity, price, total,
                       DATE_FORMAT(sale_date, '%Y-%m-%d %H:%i') AS date
                       FROM sales WHERE id=%s""", (sale_id,))
    if not sale:
        flash("Invoice not found", "error")
        return redirect(url_for("sales_page"))
    return render_template("invoice.html", sale=sale)


@app.route("/reports")
@login_required
def reports():
    today = date.today()
    monthly_sales = fetch_all("""SELECT id, medicine_name AS medicine, quantity, price, total,
        DATE_FORMAT(sale_date, '%Y-%m-%d %H:%i') AS date FROM sales
        WHERE sale_date >= %s AND sale_date < %s ORDER BY sale_date DESC""",
        (today.replace(day=1), (today.replace(day=28) + timedelta(days=4)).replace(day=1)))
    today_sales = [s for s in monthly_sales if str(s["date"])[:10] == today.isoformat()]
    medicines = fetch_all("SELECT * FROM medicines ORDER BY name")
    suppliers = fetch_all("SELECT * FROM suppliers ORDER BY name")
    expired = [m for m in medicines if m["expiry"] < today]
    total_today = sum((Decimal(s["total"]) for s in today_sales), Decimal("0.00"))
    total_month = sum((Decimal(s["total"]) for s in monthly_sales), Decimal("0.00"))
    stock_value = sum((Decimal(m["price"]) * m["stock"] for m in medicines), Decimal("0.00"))
    return render_template("reports.html", today_sales=today_sales, monthly_sales=monthly_sales,
                           total_today=total_today, total_month=total_month,
                           low_stock=[m for m in medicines if m["stock"] <= LOW_STOCK_LIMIT],
                           expired=expired, medicines=medicines, suppliers=suppliers,
                           stock_value=stock_value)


if __name__ == "__main__":
    setup_database()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
