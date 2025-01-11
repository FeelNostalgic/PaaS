function showFeedback(message, duration = 1500, isError = false) {
    const feedback = document.getElementById("feedback");

    feedback.textContent = message;

    if (isError) {
        feedback.classList.add("error");
    } else {
        feedback.classList.remove("error");
    }

    feedback.classList.add("show");

    setTimeout(() => {
        feedback.classList.remove("show");
    }, duration);
}