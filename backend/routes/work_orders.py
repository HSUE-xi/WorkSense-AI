import sqlite3

from flask import Blueprint, request
from database.db import get_connection

work_orders_bp = Blueprint("work_orders", __name__)

WORK_ORDER_STATUSES = {"PENDING", "IN_PROGRESS", "PAUSED", "DONE"}
AI_STATUSES = {"WORKING", "IDLE", "AWAY", "ABNORMAL"}
STATUS_SOURCES = {"manual", "mock_ai"}


def row_to_dict(row):
    return dict(row) if row else None


def error_response(message, status_code=400):
    return {"error": message}, status_code


def get_required_work_order(connection, work_order_id):
    return connection.execute(
        "SELECT * FROM work_orders WHERE id = ?",
        (work_order_id,)
    ).fetchone()


def get_open_time_log(connection, work_order_id):
    return connection.execute(
        """
        SELECT *
        FROM time_logs
        WHERE work_order_id = ? AND ended_at IS NULL
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (work_order_id,)
    ).fetchone()


def get_work_order_summary(connection, work_order_id=None):
    where_clause = ""
    params = ()

    if work_order_id is not None:
        where_clause = "WHERE wo.id = ?"
        params = (work_order_id,)

    rows = connection.execute(
        f"""
        SELECT
            wo.id,
            wo.work_order_no,
            wo.product_name,
            wo.standard_time,
            wo.status,
            wo.created_at,
            COALESCE(SUM(tl.duration_seconds), 0) +
                COALESCE(SUM(
                    CASE
                        WHEN tl.ended_at IS NULL
                        THEN CAST(strftime('%s', 'now') - strftime('%s', tl.started_at) AS INTEGER)
                        ELSE 0
                    END
                ), 0) AS total_seconds,
            latest_event.status AS latest_ai_status,
            latest_event.source AS latest_ai_source,
            latest_event.created_at AS latest_ai_at
        FROM work_orders wo
        LEFT JOIN time_logs tl ON tl.work_order_id = wo.id
        LEFT JOIN status_events latest_event ON latest_event.id = (
            SELECT se.id
            FROM status_events se
            WHERE se.work_order_id = wo.id
            ORDER BY se.created_at DESC, se.id DESC
            LIMIT 1
        )
        {where_clause}
        GROUP BY wo.id
        ORDER BY wo.created_at DESC, wo.id DESC
        """,
        params
    ).fetchall()

    summaries = [row_to_dict(row) for row in rows]

    if work_order_id is not None:
        return summaries[0] if summaries else None

    return summaries


@work_orders_bp.route("/api/work-orders", methods=["GET"])
def get_work_orders():
    connection = get_connection()
    work_orders = get_work_order_summary(connection)
    connection.close()

    return work_orders


@work_orders_bp.route("/api/work-orders", methods=["POST"])
def create_work_order():
    data = request.get_json() or {}
    required_fields = ["work_order_no", "product_name", "standard_time"]
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return error_response(f"缺少欄位：{', '.join(missing_fields)}")

    try:
        standard_time = int(data["standard_time"])
    except (TypeError, ValueError):
        return error_response("standard_time 必須是數字")

    if standard_time <= 0:
        return error_response("standard_time 必須大於 0")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO work_orders
            (work_order_no, product_name, standard_time)
            VALUES (?, ?, ?)
            """,
            (data["work_order_no"], data["product_name"], standard_time)
        )
        connection.commit()
        work_order = get_work_order_summary(connection, cursor.lastrowid)
    except sqlite3.IntegrityError:
        connection.close()
        return error_response("工作單編號已存在", 409)

    connection.close()

    return {
        "message": "工作單建立成功",
        "work_order": work_order
    }, 201


@work_orders_bp.route("/api/work-orders/<int:work_order_id>", methods=["GET"])
def get_work_order(work_order_id):
    connection = get_connection()
    work_order = get_work_order_summary(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    time_logs = connection.execute(
        """
        SELECT *
        FROM time_logs
        WHERE work_order_id = ?
        ORDER BY started_at DESC, id DESC
        """,
        (work_order_id,)
    ).fetchall()

    status_events = connection.execute(
        """
        SELECT *
        FROM status_events
        WHERE work_order_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (work_order_id,)
    ).fetchall()

    connection.close()

    work_order["time_logs"] = [row_to_dict(row) for row in time_logs]
    work_order["status_events"] = [row_to_dict(row) for row in status_events]

    return work_order


@work_orders_bp.route("/api/work-orders/<int:work_order_id>/status", methods=["PATCH"])
def update_work_order_status(work_order_id):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in WORK_ORDER_STATUSES:
        return error_response("不支援的工單狀態")

    connection = get_connection()
    work_order = get_required_work_order(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    connection.execute(
        "UPDATE work_orders SET status = ? WHERE id = ?",
        (status, work_order_id)
    )
    connection.commit()
    work_order = get_work_order_summary(connection, work_order_id)
    connection.close()

    return {
        "message": "工作單狀態已更新",
        "work_order": work_order
    }


@work_orders_bp.route("/api/work-orders/<int:work_order_id>/start", methods=["POST"])
def start_work_order(work_order_id):
    connection = get_connection()
    work_order = get_required_work_order(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    if work_order["status"] == "DONE":
        connection.close()
        return error_response("已完成的工作單不能重新開始")

    if get_open_time_log(connection, work_order_id):
        connection.close()
        return error_response("此工作單已經有進行中的工時紀錄")

    connection.execute(
        "INSERT INTO time_logs (work_order_id) VALUES (?)",
        (work_order_id,)
    )
    connection.execute(
        "UPDATE work_orders SET status = 'IN_PROGRESS' WHERE id = ?",
        (work_order_id,)
    )
    connection.commit()
    work_order = get_work_order_summary(connection, work_order_id)
    connection.close()

    return {
        "message": "工時已開始",
        "work_order": work_order
    }


@work_orders_bp.route("/api/work-orders/<int:work_order_id>/pause", methods=["POST"])
def pause_work_order(work_order_id):
    connection = get_connection()
    work_order = get_required_work_order(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    open_log = get_open_time_log(connection, work_order_id)

    if not open_log:
        connection.close()
        return error_response("沒有進行中的工時紀錄可以暫停")

    connection.execute(
        """
        UPDATE time_logs
        SET ended_at = CURRENT_TIMESTAMP,
            duration_seconds = CAST(strftime('%s', 'now') - strftime('%s', started_at) AS INTEGER)
        WHERE id = ?
        """,
        (open_log["id"],)
    )
    connection.execute(
        "UPDATE work_orders SET status = 'PAUSED' WHERE id = ?",
        (work_order_id,)
    )
    connection.commit()
    work_order = get_work_order_summary(connection, work_order_id)
    connection.close()

    return {
        "message": "工時已暫停",
        "work_order": work_order
    }


@work_orders_bp.route("/api/work-orders/<int:work_order_id>/finish", methods=["POST"])
def finish_work_order(work_order_id):
    connection = get_connection()
    work_order = get_required_work_order(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    if work_order["status"] == "DONE":
        connection.close()
        return error_response("工作單已經完成")

    open_log = get_open_time_log(connection, work_order_id)

    if open_log:
        connection.execute(
            """
            UPDATE time_logs
            SET ended_at = CURRENT_TIMESTAMP,
                duration_seconds = CAST(strftime('%s', 'now') - strftime('%s', started_at) AS INTEGER)
            WHERE id = ?
            """,
            (open_log["id"],)
        )

    connection.execute(
        "UPDATE work_orders SET status = 'DONE' WHERE id = ?",
        (work_order_id,)
    )
    connection.commit()
    work_order = get_work_order_summary(connection, work_order_id)
    connection.close()

    return {
        "message": "工作單已完成",
        "work_order": work_order
    }


@work_orders_bp.route("/api/work-orders/<int:work_order_id>/status-events", methods=["POST"])
def create_status_event(work_order_id):
    data = request.get_json() or {}
    status = data.get("status")
    source = data.get("source", "manual")
    note = data.get("note")

    if status not in AI_STATUSES:
        return error_response("不支援的 AI 狀態")

    if source not in STATUS_SOURCES:
        return error_response("source 只能是 manual 或 mock_ai")

    connection = get_connection()
    work_order = get_required_work_order(connection, work_order_id)

    if not work_order:
        connection.close()
        return error_response("找不到工作單", 404)

    cursor = connection.execute(
        """
        INSERT INTO status_events
        (work_order_id, status, source, note)
        VALUES (?, ?, ?, ?)
        """,
        (work_order_id, status, source, note)
    )
    connection.commit()

    status_event = connection.execute(
        "SELECT * FROM status_events WHERE id = ?",
        (cursor.lastrowid,)
    ).fetchone()
    work_order = get_work_order_summary(connection, work_order_id)
    connection.close()

    return {
        "message": "狀態事件已建立",
        "status_event": row_to_dict(status_event),
        "work_order": work_order
    }, 201
