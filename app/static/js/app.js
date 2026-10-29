const tooltipTriggerList = document.querySelectorAll('[title]');
for (const trigger of tooltipTriggerList) {
    new bootstrap.Tooltip(trigger);
}

