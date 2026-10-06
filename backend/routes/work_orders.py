from flask import Blueprint

work_orders_bp = Blueprint("work_orders", __name__)


@work_orders_bp.route("/api/work-orders", methods=["GET"])
def get_work_orders():
    return {"message": "工作單 API 正常運作"}