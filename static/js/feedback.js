function showFeedback(message, isError = false, duration = 1500) {
    const feedback = document.getElementById("feedback");

    feedback.innerHTML = message;

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

function showLoadingOverlay()
{
    const loadingOverlay = document.getElementById("loadingOverlay");
    loadingOverlay.style.display = "flex";
}

function hideLoadingOverlay()
{
    const loadingOverlay = document.getElementById("loadingOverlay");
    loadingOverlay.style.display = "none";
}