const state = { user: null, books: [], view: "catalog" };
const byId = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

function showMessage(message, success = false, target = "appMessage") {
  const element = byId(target);
  element.textContent = message || "";
  element.classList.toggle("success", Boolean(message && success));
}

function setAuthTab(tab) {
  const isLogin = tab === "login";
  byId("loginForm").hidden = !isLogin;
  byId("registerForm").hidden = isLogin;
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.authTab === tab);
  });
  showMessage("", false, "authMessage");
}

function showApp(user) {
  state.user = user;
  byId("authScreen").hidden = true;
  byId("appScreen").hidden = false;
  byId("accountBar").hidden = false;
  byId("accountName").textContent = user.name;
  byId("accountRole").textContent = user.role;
  byId("welcomeHeading").textContent = `Good to see you, ${user.name.split(" ")[0]}`;
  byId("adminTab").hidden = user.role !== "admin";
  byId("loanHeading").textContent = user.role === "admin" ? "All issued books" : "Your issued books";
  loadAppData().catch((error) => showMessage(error.message));
}

async function loadAppData() {
  const [bookData, dashboard] = await Promise.all([
    request("/api/books"),
    request("/api/dashboard"),
  ]);
  state.books = bookData.books;
  renderBooks(state.books);
  renderStats(dashboard);
  byId("fineRate").textContent = `$${dashboard.fine_per_day}`;
  populateBookOptions();
  await Promise.all([loadLoans(), loadFines()]);
}

function renderStats(data) {
  const stats = [
    ["Books in catalog", data.book_count],
    [state.user.role === "admin" ? "Active loans" : "Books you borrowed", data.active_loans],
    ["Unpaid fines", `$${data.unpaid_fines}`],
  ];
  if (state.user.role === "admin") stats.push(["Student accounts", data.student_count]);
  byId("stats").innerHTML = stats.map(([label, value]) =>
    `<div class="stat-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`
  ).join("");
}

function renderBooks(books) {
  const container = byId("bookGrid");
  if (!books.length) {
    container.innerHTML = '<p class="empty-state">No books match your search. Try another title or author.</p>';
    return;
  }
  container.innerHTML = books.map((book) => {
    const available = Number(book.available_copies) > 0;
    return `<article class="book-card">
      <span class="book-category">${esc(book.category)}</span>
      <h3>${esc(book.title)}</h3><p class="book-author">by ${esc(book.author)}</p>
      <div class="book-meta"><span>${book.isbn ? `ISBN ${esc(book.isbn)}` : "ISBN not listed"}</span>
      <span class="availability ${available ? "" : "unavailable"}">${available ? `${book.available_copies} available` : "All issued"}</span></div>
      ${state.user && available ? `<button class="button button-primary button-small issue-button" data-book-id="${Number(book.id)}" type="button">Issue to me</button>` : ""}
    </article>`;
  }).join("");
  container.querySelectorAll(".issue-button").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await request("/api/issues", {
          method: "POST",
          body: JSON.stringify({ book_id: Number(button.dataset.bookId) }),
        });
        showMessage("Book issued. Check the due date in Issued books.", true);
        await loadAppData();
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    });
  });
}

function populateBookOptions() {
  const select = byId("adminBookSelect");
  if (!select) return;
  const available = state.books.filter((book) => Number(book.available_copies) > 0);
  select.innerHTML = available.length
    ? available.map((book) => `<option value="${Number(book.id)}">${esc(book.title)} (${book.available_copies} available)</option>`).join("")
    : '<option value="">No available books</option>';
}

async function loadLoans() {
  const filter = byId("loanFilter").value;
  const query = filter ? `?status=${encodeURIComponent(filter)}` : "";
  const data = await request(`/api/issues${query}`);
  const loans = data.issues;
  const container = byId("loanList");
  if (!loans.length) {
    container.innerHTML = '<p class="empty-state">No loans to show yet. Choose a book from the catalog to get started.</p>';
    return;
  }
  container.innerHTML = `<table><thead><tr>${state.user.role === "admin" ? "<th>Student</th>" : ""}
    <th>Book</th><th>Issued</th><th>Due date</th><th>Status / fine</th><th>Action</th></tr></thead><tbody>
    ${loans.map((loan) => {
      const returned = Boolean(loan.returned_at);
      const overdue = !returned && loan.overdue_days > 0;
      const status = returned ? `Returned ${esc(loan.returned_at)}` : overdue ? `${loan.overdue_days} days overdue · $${esc(loan.fine_amount)}` : "On loan";
      return `<tr>${state.user.role === "admin" ? `<td>${esc(loan.student_name)}<br><span class="muted">${esc(loan.student_email)}</span></td>` : ""}
        <td>${esc(loan.book_title)}</td><td>${esc(loan.issued_at)}</td><td>${esc(loan.due_at)}</td>
        <td><span class="status-pill ${overdue ? "overdue" : ""}">${status}</span></td>
        <td>${returned ? "—" : `<button class="button button-dark button-small return-button" data-loan-id="${Number(loan.id)}" type="button">Return</button>`}</td></tr>`;
    }).join("")}</tbody></table>`;
  container.querySelectorAll(".return-button").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const result = await request(`/api/issues/${Number(button.dataset.loanId)}/return`, { method: "POST" });
        showMessage(result.fine_amount === "0.00"
          ? "Book returned. No late fine was due."
          : `Book returned. A late fine of $${result.fine_amount} was added.`, true);
        await loadAppData();
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    });
  });
}

async function loadFines() {
  const data = await request("/api/fines");
  const container = byId("fineList");
  if (!data.fines.length) {
    container.innerHTML = '<p class="empty-state">No fines recorded. Return books by their due dates to keep it that way.</p>';
    return;
  }
  container.innerHTML = `<table><thead><tr>${state.user.role === "admin" ? "<th>Student</th>" : ""}
    <th>Book</th><th>Days late</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead><tbody>
    ${data.fines.map((fine) => `<tr>${state.user.role === "admin" ? `<td>${esc(fine.student_name)}<br><span class="muted">${esc(fine.student_email)}</span></td>` : ""}
      <td>${esc(fine.book_title)}</td><td>${esc(fine.days_overdue)}</td><td>$${esc(fine.amount)}</td>
      <td><span class="status-pill ${fine.paid ? "" : "overdue"}">${fine.paid ? "Paid" : "Unpaid"}</span></td>
      <td>${fine.paid ? "—" : `<button class="button button-dark button-small pay-button" data-fine-id="${Number(fine.id)}" type="button">Mark paid</button>`}</td></tr>`
    ).join("")}</tbody></table>`;
  container.querySelectorAll(".pay-button").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await request(`/api/fines/${Number(button.dataset.fineId)}/pay`, { method: "POST" });
        showMessage("Fine marked as paid.", true);
        await loadAppData();
      } catch (error) {
        showMessage(error.message);
      }
    });
  });
}

document.querySelectorAll("[data-auth-tab]").forEach((button) =>
  button.addEventListener("click", () => setAuthTab(button.dataset.authTab))
);

byId("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const result = await request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form)),
    });
    showApp(result.user);
    showMessage("");
  } catch (error) {
    showMessage(error.message, false, "authMessage");
  }
});

byId("registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const result = await request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form)),
    });
    showApp(result.user);
    showMessage(result.user.role === "admin"
      ? "Your account is ready. You are the library administrator."
      : "Your student account is ready.", true);
  } catch (error) {
    showMessage(error.message, false, "authMessage");
  }
});

byId("logoutButton").addEventListener("click", async () => {
  try {
    await request("/api/auth/logout", { method: "POST" });
    window.location.reload();
  } catch (error) {
    showMessage(error.message);
  }
});

document.querySelectorAll(".nav-tab").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    document.querySelectorAll(".nav-tab").forEach((tab) =>
      tab.classList.toggle("active", tab === button)
    );
    document.querySelectorAll(".view-panel").forEach((panel) =>
      panel.hidden = panel.id !== `view-${state.view}`
    );
    showMessage("");
  });
});

byId("bookSearch").addEventListener("input", async (event) => {
  try {
    const data = await request(`/api/books?q=${encodeURIComponent(event.target.value)}`);
    state.books = data.books;
    renderBooks(state.books);
    populateBookOptions();
  } catch (error) {
    showMessage(error.message);
  }
});

byId("loanFilter").addEventListener("change", () => loadLoans().catch((error) => showMessage(error.message)));

byId("addBookForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form);
  payload.total_copies = Number(payload.total_copies);
  try {
    await request("/api/books", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    event.currentTarget.elements.category.value = "General";
    event.currentTarget.elements.total_copies.value = "1";
    showMessage("Book added to the catalog.", true);
    await loadAppData();
  } catch (error) {
    showMessage(error.message);
  }
});

byId("adminIssueForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  payload.book_id = Number(payload.book_id);
  try {
    await request("/api/issues", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    showMessage("Book issued to the student.", true);
    await loadAppData();
  } catch (error) {
    showMessage(error.message);
  }
});

request("/api/auth/me")
  .then((result) => showApp(result.user))
  .catch(() => {
    byId("authScreen").hidden = false;
    byId("appScreen").hidden = true;
  });
