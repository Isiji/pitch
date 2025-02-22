document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('pitchForm');
    const generateButton = document.getElementById('generateButton');
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    const pitchResult = document.getElementById('pitchResult');
    const pitchContent = document.getElementById('pitchContent');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        generateButton.disabled = true;
        generateButton.textContent = 'Generating Pitch...';
        errorAlert.style.display = 'none';
        pitchResult.style.display = 'none';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            console.log('Submitting form data:', data);
            const response = await fetch('/generate-pitch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to generate pitch');
            }

            const result = await response.json();
            console.log('Response data:', result);

            if (!result.pitch) {
                throw new Error('No pitch was generated');
            }

            pitchContent.textContent = result.pitch;
            pitchResult.style.display = 'block';
        } catch (error) {
            console.error('Error in handleSubmit:', error);
            errorMessage.textContent = error.message;
            errorAlert.style.display = 'block';
        } finally {
            generateButton.disabled = false;
            generateButton.textContent = 'Generate Pitch';
        }
    });
});