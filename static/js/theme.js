// Light theme is now the default theme for the entire application
document.addEventListener('DOMContentLoaded', function() {
    // Apply light theme styling
    document.body.classList.add('light-theme');

    // Initialize feather icons if they exist
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
});