const statusLabels = {
    PENDING: "待開始",
    IN_PROGRESS: "進行中",
    PAUSED: "已暫停",
    DONE: "已完成",
};

const aiStatusLabels = {
    WORKING: "作業中",
    IDLE: "閒置",
    AWAY: "離開",
    ABNORMAL: "異常",
};

function formatSeconds(seconds) {
    const value = Number(seconds || 0);
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const remainSeconds = value % 60;

    if (hours > 0) {
        return `${hours}時 ${minutes}分 ${remainSeconds}秒`;
    }

    if (minutes > 0) {
        return `${minutes}分 ${remainSeconds}秒`;
    }

    return `${remainSeconds}秒`;
}

function formatPercent(workOrder) {
    const standard = Number(workOrder.standard_time || 0);
    const actual = Number(workOrder.total_seconds || 0);

    if (standard <= 0 || actual <= 0) {
        return "-";
    }

    return `${Math.round((standard / actual) * 100)}%`;
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
        },
        ...options,
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "操作失敗");
    }

    return data;
}

async function loadWorkOrders() {
    return apiRequest("/api/work-orders");
}

function setMessage(id, message) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = message || "";
    }
}

function renderOperatorOrders(workOrders) {
    const container = document.getElementById("operatorOrders");

    if (!container) {
        return;
    }

    if (workOrders.length === 0) {
        container.innerHTML = `<p class="message">目前還沒有工單，先建立第一張工單。</p>`;
        return;
    }

    container.innerHTML = workOrders.map((workOrder) => `
        <article class="order-card">
            <div>
                <h3>${workOrder.work_order_no}</h3>
                <p class="meta">${workOrder.product_name}</p>
            </div>
            <span class="status-pill status-${workOrder.status}">
                ${statusLabels[workOrder.status] || workOrder.status}
            </span>
            <div class="meta">
                <span>標準工時：${formatSeconds(workOrder.standard_time)}</span>
                <span>累積工時：${formatSeconds(workOrder.total_seconds)}</span>
                <span>AI 狀態：${aiStatusLabels[workOrder.latest_ai_status] || "尚無資料"}</span>
            </div>
            <div class="actions">
                <button data-action="start" data-id="${workOrder.id}">開始/繼續</button>
                <button class="warning-button" data-action="pause" data-id="${workOrder.id}">暫停</button>
                <button class="danger-button" data-action="finish" data-id="${workOrder.id}">完成</button>
            </div>
            <div class="ai-actions">
                ${Object.keys(aiStatusLabels).map((status) => `
                    <button class="ghost-button" data-ai-status="${status}" data-id="${workOrder.id}">
                        ${aiStatusLabels[status]}
                    </button>
                `).join("")}
            </div>
        </article>
    `).join("");
}

async function refreshOperator() {
    try {
        const workOrders = await loadWorkOrders();
        renderOperatorOrders(workOrders);
        setMessage("operatorMessage", `已載入 ${workOrders.length} 張工單`);
    } catch (error) {
        setMessage("operatorMessage", error.message);
    }
}

function setupOperatorPage() {
    const form = document.getElementById("createOrderForm");
    const refreshButton = document.getElementById("refreshOrders");
    const container = document.getElementById("operatorOrders");

    if (!form || !container) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        try {
            await apiRequest("/api/work-orders", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            form.reset();
            setMessage("operatorMessage", "工作單已建立");
            await refreshOperator();
        } catch (error) {
            setMessage("operatorMessage", error.message);
        }
    });

    refreshButton.addEventListener("click", refreshOperator);

    container.addEventListener("click", async (event) => {
        const button = event.target.closest("button");

        if (!button) {
            return;
        }

        const id = button.dataset.id;

        try {
            if (button.dataset.action) {
                await apiRequest(`/api/work-orders/${id}/${button.dataset.action}`, {
                    method: "POST",
                });
            }

            if (button.dataset.aiStatus) {
                await apiRequest(`/api/work-orders/${id}/status-events`, {
                    method: "POST",
                    body: JSON.stringify({
                        status: button.dataset.aiStatus,
                        source: "manual",
                    }),
                });
            }

            await refreshOperator();
        } catch (error) {
            setMessage("operatorMessage", error.message);
        }
    });

    refreshOperator();
}

function renderDashboardStats(workOrders) {
    const container = document.getElementById("dashboardStats");

    if (!container) {
        return;
    }

    const total = workOrders.length;
    const active = workOrders.filter((item) => item.status === "IN_PROGRESS").length;
    const done = workOrders.filter((item) => item.status === "DONE").length;
    const totalSeconds = workOrders.reduce((sum, item) => sum + Number(item.total_seconds || 0), 0);

    container.innerHTML = `
        <div class="stat-card"><span>工單總數</span><strong>${total}</strong></div>
        <div class="stat-card"><span>進行中</span><strong>${active}</strong></div>
        <div class="stat-card"><span>已完成</span><strong>${done}</strong></div>
        <div class="stat-card"><span>總工時</span><strong>${formatSeconds(totalSeconds)}</strong></div>
    `;
}

function renderDashboardRows(workOrders) {
    const body = document.getElementById("dashboardRows");

    if (!body) {
        return;
    }

    if (workOrders.length === 0) {
        body.innerHTML = `<tr><td colspan="6">目前沒有工單資料。</td></tr>`;
        return;
    }

    body.innerHTML = workOrders.map((workOrder) => `
        <tr>
            <td>${workOrder.work_order_no}</td>
            <td>${workOrder.product_name}</td>
            <td><span class="status-pill status-${workOrder.status}">${statusLabels[workOrder.status] || workOrder.status}</span></td>
            <td>${formatSeconds(workOrder.total_seconds)}</td>
            <td>${formatPercent(workOrder)}</td>
            <td>${aiStatusLabels[workOrder.latest_ai_status] || "尚無資料"}</td>
        </tr>
    `).join("");
}

async function refreshDashboard() {
    try {
        const workOrders = await loadWorkOrders();
        renderDashboardStats(workOrders);
        renderDashboardRows(workOrders);
        setMessage("dashboardMessage", `最後更新：${new Date().toLocaleTimeString()}`);
    } catch (error) {
        setMessage("dashboardMessage", error.message);
    }
}

function setupDashboardPage() {
    const refreshButton = document.getElementById("refreshDashboard");

    if (!refreshButton) {
        return;
    }

    refreshButton.addEventListener("click", refreshDashboard);
    refreshDashboard();
    setInterval(refreshDashboard, 10000);
}

setupOperatorPage();
setupDashboardPage();
