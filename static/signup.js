// Show / Hide password
const togglePassword = document.getElementById("togglePassword");
const password = document.getElementById("password");

togglePassword.addEventListener("click", () => {
    password.type = password.type === "password" ? "text" : "password";
    togglePassword.textContent =
        password.type === "password" ? "👁️" : "🙈";
});

// Validation + animation
const signupBtn = document.getElementById("signupBtn");

signupBtn.addEventListener("click", (e) => {
    const pwd = document.getElementById("password").value;
    const confirmPwd = document.getElementById("confirmPassword").value;

    if (pwd !== confirmPwd) {
        alert("Passwords do not match!");
        e.preventDefault();
        return;
    }

    signupBtn.innerHTML = "⏳ Creating account...";
});
// Link to login page
const loginLink = document.getElementById("loginLink");