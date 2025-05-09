// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add fade-in animation to main content
    const mainContent = document.querySelector('main');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }

    // Add active class to current nav link
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('nav a');
    
    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        if (currentPath === linkPath || 
            (linkPath !== '/' && currentPath.startsWith(linkPath))) {
            link.classList.add('active');
        }
    });

    // Form validation
    const summonerForm = document.querySelector('.summoner-form');
    if (summonerForm) {
        summonerForm.addEventListener('submit', function(e) {
            const summonerName = document.getElementById('summoner_name').value;
            const tagline = document.getElementById('tagline').value;
            const region = document.getElementById('region').value;
            
            if (!summonerName || !tagline || !region) {
                e.preventDefault();
                alert('Please fill in all fields');
            }
        });
    }

    // Add error/success message auto-hide
    const messages = document.querySelectorAll('.error-message, .success-message');
    if (messages.length > 0) {
        setTimeout(() => {
            messages.forEach(msg => {
                msg.style.opacity = '0';
                msg.style.transition = 'opacity 0.5s ease';
                setTimeout(() => {
                    msg.style.display = 'none';
                }, 500);
            });
        }, 5000);
    }
});

// Function to copy match ID to clipboard
function copyMatchId(matchId) {
    navigator.clipboard.writeText(matchId).then(() => {
        alert('Match ID copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy match ID: ', err);
    });
}

// Function to load more matches
function loadMoreMatches(summonerName, tagline, region, offset) {
    fetch(`/api/matches/${summonerName}/${tagline}/${region}?offset=${offset}`)
        .then(response => response.json())
        .then(data => {
            const matchesList = document.querySelector('.matches-list');
            
            if (data.matches && data.matches.length > 0) {
                data.matches.forEach(match => {
                    const matchElement = createMatchElement(match);
                    matchesList.appendChild(matchElement);
                });
                
                // Update the load more button's offset
                const loadMoreBtn = document.getElementById('load-more-btn');
                if (loadMoreBtn) {
                    loadMoreBtn.setAttribute('data-offset', offset + data.matches.length);
                }
            } else {
                const loadMoreBtn = document.getElementById('load-more-btn');
                if (loadMoreBtn) {
                    loadMoreBtn.textContent = 'No more matches';
                    loadMoreBtn.disabled = true;
                }
            }
        })
        .catch(error => {
            console.error('Error loading more matches:', error);
        });
}

// Helper function to create match element
function createMatchElement(match) {
    const div = document.createElement('div');
    div.className = `match-card ${match.win ? 'win' : 'loss'}`;
    
    div.innerHTML = `
        <div class="match-champion">
            <img src="https://ddragon.leagueoflegends.com/cdn/11.14.1/img/champion/${match.champion_name}.png" alt="${match.champion_name}" onerror="this.src='/static/images/default-champion.png'">
        </div>
        <div class="match-result">
            <h3>${match.win ? 'Victory' : 'Defeat'}</h3>
            <p>${match.game_start.split('T')[0]}</p>
        </div>
        <div class="match-stats">
            <p class="kda">${match.kills}/${match.deaths}/${match.assists}</p>
            <p class="kda-ratio">${((match.kills + match.assists) / Math.max(1, match.deaths)).toFixed(2)} KDA</p>
        </div>
        <div class="match-details">
            ${match.damage_per_minute ? `<p>${Math.round(match.damage_per_minute * 10) / 10} DMG/min</p>` : ''}
            <p>${match.gold_earned} gold</p>
        </div>
        <div class="match-actions">
            <a href="/match/${match.match_id}" class="btn details-btn">Details</a>
        </div>
    `;
    
    return div;
}