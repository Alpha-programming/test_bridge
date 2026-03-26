console.log("IELTS JS Loaded");

// Example: highlight active nav
document.addEventListener("DOMContentLoaded", function () {
    const links = document.querySelectorAll(".nav-link");

    links.forEach(link => {
        if (link.href === window.location.href) {
            link.classList.add("text-info");
        }
    });
});

const searchInput = document.querySelector("input[name='q']");

if (searchInput) {
    searchInput.addEventListener("keyup", function () {
        const value = this.value.toLowerCase();

        document.querySelectorAll(".test-card").forEach(card => {
            const text = card.innerText.toLowerCase();

            if (text.includes(value)) {
                card.style.display = "flex";
            } else {
                card.style.display = "none";
            }
        });
    });
}

document.querySelectorAll(".answer-input").forEach(el => {
    el.addEventListener("change", function () {

        let value;

        if (this.type === "radio") {
            value = this.value;
        } else {
            value = this.value;
        }

        fetch("/ielts/save-answer/", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": getCookie("csrftoken")
            },
            body: `question_id=${this.dataset.question}&answer=${value}&user_test_id=${this.dataset.userTest}`
        });
    });
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        document.cookie.split(";").forEach(cookie => {
            const c = cookie.trim();
            if (c.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
            }
        });
    }
    return cookieValue;
}

const ctx = document.getElementById("scoreChart");

if (ctx) {
    const data = JSON.parse('{{ progress_data|safe }}');

    new Chart(ctx, {
        type: "line",
        data: {
            labels: data.map((_, i) => i + 1),
            datasets: [{
                label: "Band Score",
                data: data,
                fill: false,
                tension: 0.3
            }]
        }
    });
}

