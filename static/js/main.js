// Add to cart functionality
function updateQuantity(input) {
    const minValue = 1;
    const maxValue = 10;
    
    if (input.value < minValue) {
        input.value = minValue;
    } else if (input.value > maxValue) {
        input.value = maxValue;
    }
}

// Flash message auto-hide
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.display = 'none';
        }, 3000);
    });
}); 