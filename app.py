from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = "medical-store-secret"

# =========================================================
# TEMPORARY DATA
# MySQL will replace these later.
# =========================================================

users = {
    "admin": "admin123"
}

medicines = [
    {
        "id": 1,
        "name": "Paracetamol",
        "category": "Tablet",
        "price": 20.0,
        "stock": 50,
        "expiry": "2027-05-15"
    },
    {
        "id": 2,
        "name": "Amoxicillin",
        "category": "Capsule",
        "price": 85.0,
        "stock": 12,
        "expiry": "2026-12-20"
    },
    {
        "id": 3,
        "name": "Cough Syrup",
        "category": "Syrup",
        "price": 120.0,
        "stock": 5,
        "expiry": "2026-11-10"
    }
]

suppliers = [
    {
        "id": 1,
        "name": "ABC Pharma",
        "contact": "9876543210",
        "address": "Mumbai"
    },
    {
        "id": 2,
        "name": "MediSupply Pvt Ltd",
        "contact": "9123456789",
        "address": "Vasai"
    }
]

sales = []


# =========================================================
# LOGIN DECORATOR
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("logged_in"):
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# LOGIN
# =========================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username in users and users[username] == password:

            session["logged_in"] = True
            session["username"] = username

            return redirect(url_for("dashboard"))

        flash("Invalid username or password", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# CHANGE PASSWORD
# =========================================================

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():

    username = session["username"]

    if request.method == "POST":

        current = request.form.get("current_password")
        new = request.form.get("new_password")
        confirm = request.form.get("confirm_password")

        if users[username] != current:

            flash("Current password is incorrect", "error")

        elif len(new) < 4:

            flash("Password must contain at least 4 characters", "error")

        elif new != confirm:

            flash("Passwords do not match", "error")

        else:

            users[username] = new

            flash("Password changed successfully", "success")

            return redirect(url_for("dashboard"))

    return render_template("change_password.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    total_medicines = len(medicines)

    total_stock = sum(
        medicine["stock"]
        for medicine in medicines
    )

    low_stock = [
        medicine
        for medicine in medicines
        if medicine["stock"] <= 10
    ]

    total_sales = sum(
        sale["total"]
        for sale in sales
    )

    return render_template(
        "dashboard.html",
        total_medicines=total_medicines,
        total_stock=total_stock,
        low_stock=len(low_stock),
        total_sales=total_sales
    )


# =========================================================
# MEDICINES
# =========================================================

@app.route("/medicines", methods=["GET", "POST"])
@login_required
def medicines_page():

    if request.method == "POST":

        name = request.form.get("name")
        category = request.form.get("category")
        price = float(request.form.get("price", 0))
        stock = int(request.form.get("stock", 0))
        expiry = request.form.get("expiry")

        new_id = max(
            [m["id"] for m in medicines],
            default=0
        ) + 1

        medicines.append({
            "id": new_id,
            "name": name,
            "category": category,
            "price": price,
            "stock": stock,
            "expiry": expiry
        })

        flash("Medicine added successfully", "success")

        return redirect(url_for("medicines_page"))

    search = request.args.get("search", "").strip().lower()

    if search:

        displayed = [
            m for m in medicines
            if search in m["name"].lower()
        ]

    else:

        displayed = medicines

    return render_template(
        "medicines.html",
        medicines=displayed
    )


@app.route("/medicine/edit/<int:medicine_id>", methods=["GET", "POST"])
@login_required
def edit_medicine(medicine_id):

    medicine = next(
        (m for m in medicines if m["id"] == medicine_id),
        None
    )

    if not medicine:

        flash("Medicine not found", "error")

        return redirect(url_for("medicines_page"))

    if request.method == "POST":

        medicine["name"] = request.form.get("name")
        medicine["category"] = request.form.get("category")
        medicine["price"] = float(request.form.get("price", 0))
        medicine["stock"] = int(request.form.get("stock", 0))
        medicine["expiry"] = request.form.get("expiry")

        flash("Medicine updated successfully", "success")

        return redirect(url_for("medicines_page"))

    return render_template(
        "edit_medicine.html",
        medicine=medicine
    )


@app.route("/medicine/delete/<int:medicine_id>")
@login_required
def delete_medicine(medicine_id):

    global medicines

    medicines = [
        m for m in medicines
        if m["id"] != medicine_id
    ]

    flash("Medicine deleted successfully", "success")

    return redirect(url_for("medicines_page"))


# =========================================================
# SUPPLIERS
# =========================================================

@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers_page():

    if request.method == "POST":

        name = request.form.get("name")
        contact = request.form.get("contact")
        address = request.form.get("address")

        new_id = max(
            [s["id"] for s in suppliers],
            default=0
        ) + 1

        suppliers.append({
            "id": new_id,
            "name": name,
            "contact": contact,
            "address": address
        })

        flash("Supplier added successfully", "success")

        return redirect(url_for("suppliers_page"))

    return render_template(
        "suppliers.html",
        suppliers=suppliers
    )


@app.route("/supplier/edit/<int:supplier_id>", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id):

    supplier = next(
        (s for s in suppliers if s["id"] == supplier_id),
        None
    )

    if not supplier:

        flash("Supplier not found", "error")

        return redirect(url_for("suppliers_page"))

    if request.method == "POST":

        supplier["name"] = request.form.get("name")
        supplier["contact"] = request.form.get("contact")
        supplier["address"] = request.form.get("address")

        flash("Supplier updated successfully", "success")

        return redirect(url_for("suppliers_page"))

    return render_template(
        "edit_supplier.html",
        supplier=supplier
    )


@app.route("/supplier/delete/<int:supplier_id>")
@login_required
def delete_supplier(supplier_id):

    global suppliers

    suppliers = [
        s for s in suppliers
        if s["id"] != supplier_id
    ]

    flash("Supplier deleted successfully", "success")

    return redirect(url_for("suppliers_page"))


# =========================================================
# SALES & BILLING
# =========================================================

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales_page():

    if request.method == "POST":

        medicine_id = int(
            request.form.get("medicine_id")
        )

        quantity = int(
            request.form.get("quantity")
        )

        medicine = next(
            (
                m for m in medicines
                if m["id"] == medicine_id
            ),
            None
        )

        if not medicine:

            flash("Medicine not found", "error")

            return redirect(url_for("sales_page"))

        if quantity <= 0:

            flash("Quantity must be greater than zero", "error")

            return redirect(url_for("sales_page"))

        if quantity > medicine["stock"]:

            flash("Insufficient stock", "error")

            return redirect(url_for("sales_page"))

        total = medicine["price"] * quantity

        medicine["stock"] -= quantity

        sale = {
            "id": len(sales) + 1,
            "medicine": medicine["name"],
            "quantity": quantity,
            "price": medicine["price"],
            "total": total,
            "date": date.today().strftime("%Y-%m-%d")
        }

        sales.append(sale)

        flash("Sale recorded and stock updated", "success")

        return redirect(url_for("sales_page"))

    return render_template(
        "sales.html",
        medicines=medicines,
        sales=sales
    )


@app.route("/invoice/<int:sale_id>")
@login_required
def invoice(sale_id):

    sale = next(
        (s for s in sales if s["id"] == sale_id),
        None
    )

    if not sale:

        flash("Invoice not found", "error")

        return redirect(url_for("sales_page"))

    return render_template(
        "invoice.html",
        sale=sale
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@login_required
def reports():

    today = date.today()

    today_string = today.strftime("%Y-%m-%d")

    current_month = today.strftime("%Y-%m")

    today_sales = [
        s for s in sales
        if s["date"] == today_string
    ]

    monthly_sales = [
        s for s in sales
        if s["date"].startswith(current_month)
    ]

    low_stock = [
        m for m in medicines
        if m["stock"] <= 10
    ]

    expired = []

    for medicine in medicines:

        try:

            expiry_date = datetime.strptime(
                medicine["expiry"],
                "%Y-%m-%d"
            ).date()

            if expiry_date < today:
                expired.append(medicine)

        except ValueError:

            pass

    total_today = sum(
        s["total"]
        for s in today_sales
    )

    total_month = sum(
        s["total"]
        for s in monthly_sales
    )

    stock_value = sum(
        m["price"] * m["stock"]
        for m in medicines
    )

    return render_template(
        "reports.html",
        today_sales=today_sales,
        monthly_sales=monthly_sales,
        total_today=total_today,
        total_month=total_month,
        low_stock=low_stock,
        expired=expired,
        medicines=medicines,
        suppliers=suppliers,
        stock_value=stock_value
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)