// ---------------- PASSWORD TOGGLE ----------------
const togglePassword = document.getElementById("togglePassword");
const password = document.getElementById("password");

if (togglePassword) {
    togglePassword.addEventListener("click", () => {
        password.type = password.type === "password" ? "text" : "password";
        togglePassword.textContent =
            password.type === "password" ? "👁️" : "🙈";
    });
}

// ---------------- DO NOT TOUCH LOGIN BUTTON ----------------
// ❌ No "Checking..."
// ❌ No disabling button
// ❌ No preventDefault()
// Backend controls authentication

// ---------------- SOCIAL BUTTONS (UI ONLY) ----------------
const googleBtn = document.getElementById("googleBtn");
if (googleBtn) {
    googleBtn.onclick = () =>
        alert("Google login will be implemented using OAuth 2.0");
}

const facebookBtn = document.getElementById("facebookBtn");
if (facebookBtn) {
    facebookBtn.onclick = () =>
        alert("Facebook login will be implemented using OAuth 2.0");
}
