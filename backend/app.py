from flask import Flask, render_template
from routes.work_orders import work_orders_bp

app = Flask(__name__)

app.register_blueprint(work_orders_bp)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/operator")
def operator():
    return render_template("operator.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)
