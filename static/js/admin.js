// Admin interface interactions
document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/guests')
        .then(response => response.json())
        .then(guests => {
            const container = document.getElementById('guestList');
            guests.forEach(guest => {
                const card = document.createElement('div');
                card.className = `col-12 guest-card ${guest.status}`;
                card.innerHTML = `
                    <div class="card h-100">
                        <div class="card-body">
                            <h5>${guest.name}</h5>
                            <p class="text-muted">${guest.phone}</p>
                            ${guest.status === 'pending' ? 
                                `<button onclick="approveGuest(${guest.id})" class="btn btn-success">Approve</button>` : 
                                `<span class="badge bg-success">Approved</span>`}
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        });
});

function approveGuest(id) {
    fetch(`/guests/${id}/approve`, {
        method: 'PATCH',
        headers: {
            'Authorization': 'Basic ' + btoa('${os.environ.get('ADMIN_USER')}:${os.environ.get('ADMIN_PASS')}')
        }
    }).then(() => window.location.reload());
}
