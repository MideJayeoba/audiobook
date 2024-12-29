document.getElementById('uploadForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    const formData = new FormData(this); // Create a FormData object from the form

    fetch('/upload/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        const resultDiv = document.getElementById('result');
        if (data.txt_file) {
            resultDiv.innerHTML = `<p>${data.message}</p><p>Text file created: <a href="/media/${data.txt_file}" target="_blank">${data.txt_file}</a></p>`;
        } else {
            resultDiv.innerHTML = `<p>Error: ${data.error || 'Unknown error'}</p>`;
        }
    })
    .catch(error => {
        document.getElementById('result').innerHTML = `<p>Error: ${error.message}</p>`;
    });
});
