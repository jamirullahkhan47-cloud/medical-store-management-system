from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import date

app = Flask(__name__)
app.secret_key = "medical-store-secret-key"

# ---------------- SAMPLE DATA ----------------

medicines = [
    {
        "id": 1,
        "name": "Paracetamol",
        "category": "Tablet",
        "price": 20.00,
        "stock": 50,
        "expiry": "2027-05-15"
    },
    {
        "id": 2,
        "name": "Amoxicillin",
        "category": "Capsule",
        "price": 85.00,
        "stock": 12,
        "expiry": "2026-12-20"
    },
    {
        "id": 3,
        "name": "Cough Syrup",
        "category": "Syrup",
        "price": 120.00,
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


# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":

            session["logged_in"] = True
            session["username"] = username

            return redirect(url_for("dashboard"))

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- LOGIN CHECK ----------------

def require_login():

    return session.get("logged_in") is True


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if not require_login():
        return redirect(url_for("login"))

    total_medicines = len(medicines)

    total_stock = sum(
        medicine["stock"]
        for medicine in medicines
    )

    low_stock = len([
        medicine
        for medicine in medicines
        if medicine["stock"] <= 10
    ])

    total_sales = sum(
        sale["total"]
        for sale in sales
    )

    return render_template(
        "dashboard.html",
        total_medicines=total_medicines,
        total_stock=total_stock,
        low_stock=low_stock,
        total_sales=total_sales
    )


# ---------------- MEDICINE MANAGEMENT ----------------

@app.route("/medicines", methods=["GET", "POST"])
def medicines_page():

    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get("name")
        category = request.form.get("category")
        price = float(request.form.get("price", 0))
        stock = int(request.form.get("stock", 0))
        expiry = request.form.get("expiry")

        new_id = max(
            [medicine["id"] for medicine in medicines],
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

        flash("Medicine added successfully")

        return redirect(url_for("medicines_page"))

    search = request.args.get("search", "").lower()

    if search:

        filtered_medicines = [
            medicine
            for medicine in medicines
            if search in medicine["name"].lower()
        ]

    else:

        filtered_medicines = medicines

    return render_template(
        "medicines.html",
        medicines=filtered_medicines
    )


@app.route("/medicine/delete/<int:medicine_id>")
def delete_medicine(medicine_id):

    if not require_login():
        return redirect(url_for("login"))

    global medicines

    medicines = [
        medicine
        for medicine in medicines
        if medicine["id"] != medicine_id
    ]

    flash("Medicine deleted successfully")

    return redirect(url_for("medicines_page"))


# ---------------- SUPPLIER MANAGEMENT ----------------

@app.route("/suppliers", methods=["GET", "POST"])
def suppliers_page():

    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get("name")
        contact = request.form.get("contact")
        address = request.form.get("address")

        new_id = max(
            [supplier["id"] for supplier in suppliers],
            default=0
        ) + 1

        suppliers.append({
            "id": new_id,
            "name": name,
            "contact": contact,
            "address": address
        })

        flash("Supplier added successfully")

        return redirect(url_for("suppliers_page"))

    return render_template(
        "suppliers.html",
        suppliers=suppliers
    )


# ---------------- SALES & BILLING ----------------

@app.route("/sales", methods=["GET", "POST"])
def sales_page():

    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":

        medicine_id = int(
            request.form.get("medicine_id")
        )

        quantity = int(
            request.form.get("quantity")
        )

        medicine = next(
            (
                medicine
                for medicine in medicines
                if medicine["id"] == medicine_id
            ),
            None
        )

        if medicine is None:

            flash("Medicine not found")

            return redirect(url_for("sales_page"))

        if quantity <= 0:

            flash("Invalid quantity")

            return redirect(url_for("sales_page"))

        if quantity > medicine["stock"]:

            flash("Insufficient stock")

            return redirect(url_for("sales_page"))

        total = medicine["price"] * quantity

        medicine["stock"] -= quantity

        sales.append({
            "medicine": medicine["name"],
            "quantity": quantity,
            "price": medicine["price"],
            "total": total,
            "date": date.today().strftime("%Y-%m-%d")
        })

        flash("Sale recorded successfully")

        return redirect(url_for("sales_page"))

    return render_template(
        "sales.html",
        medicines=medicines,
        sales=sales
    )


# ---------------- REPORTS ----------------

@app.route("/reports")
def reports():

    if not require_login():
        return redirect(url_for("login"))

    total_sales = sum(
        sale["total"]
        for sale in sales
    )

    low_stock = [
        medicine
        for medicine in medicines
        if medicine["stock"] <= 10
    ]

    today = date.today().strftime("%Y-%m-%d")

    today_sales = [
        sale
        for sale in sales
        if sale["date"] == today
    ]

    return render_template(
        "reports.html",
        sales=sales,
        total_sales=total_sales,
        low_stock=low_stock,
        today_sales=today_sales
    )


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)