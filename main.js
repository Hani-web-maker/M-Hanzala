// Helper function for Counter Animation
// No longer needed, but kept as a comment for context
// function animateCounter(element, target, duration = 2000) {
//     let start = 0;
//     const increment = target / (duration / 16);
//     const timer = setInterval(() => {
//         start += increment;
//         if (start >= target) {
//             element.textContent = target;
//             clearInterval(timer);
//         } else {
//             element.textContent = Math.floor(start);
//         }
//     }, 16);
// }

// Options for Intersection Observer
const observerOptions = {
    threshold: 0.2,
    rootMargin: '0px'
};

// Intersection Observer instance
const contentObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            if (entry.target.classList.contains('skill-level')) {
                const progressBar = entry.target.querySelector('.skill-progress');
                const percentage = entry.target.getAttribute('data-percentage');
                progressBar.style.width = percentage + '%';
            }
            entry.target.classList.add('fade-in');
            contentObserver.unobserve(entry.target);
        }
    });
}, observerOptions);

// Journey Data (simplified for vertical timeline)
const journeyData = [
    {
        year: ' Starting of 2024',
        title: 'Journey Starts: Web Dev Basics',
        description: 'Began with HTML, CSS, and JavaScript fundamentals, laying the groundwork for web development.',
        iconClass: 'fas fa-rocket'
    },
    {
        year: '3 Months of Lerning, 2024',
        title: 'SEO Skill Acquisition',
        description: 'Dived deep into Search Engine Optimization to enhance website visibility and ranking.',
        iconClass: 'fas fa-search'
    },
    {
        year: ' Starting Of 2025',
        title: 'PHP & Backend Development',
        description: 'Learned PHP for server-side development, focusing on database interactions and dynamic web applications.',
        iconClass: 'fab fa-php'
    },
    {
        year: '2025',
        title: 'First Professional Role',
        description: 'Gained hands-on experience at a web development agency, working on live WordPress and PHP projects.',
        iconClass: 'fas fa-laptop-code'
    },
    {
        year: '3 Months Passed, 2025',
        title: 'Full Stack Development Mastery',
        description: 'Mastered React and Node.js, building robust and scalable full-stack applications with modern frameworks.',
        iconClass: 'fas fa-code-branch'
    },
    {
        year: 'Mid of 2025',
        title: 'Freelance Success & Growth',
        description: 'Launched a successful freelance career, collaborating with diverse international clients.',
        iconClass: 'fas fa-rocket'
    },
    {
        year: 'Present',
        title: 'Full Stack Developer',
        description: 'Currently leading complex projects, mentoring junior developers, and integrating advanced SEO strategies into every development phase.',
        iconClass: 'fas fa-award'
    }
];

// Function to dynamically render journey timeline cards
function renderJourneyTimelineCards() {
    const timelineContainer = document.querySelector('.journey-timeline-container');
    if (timelineContainer) {
        timelineContainer.innerHTML = ''; // Clear existing content

        journeyData.forEach((item, index) => {
            const journeyCard = document.createElement('div');
            journeyCard.classList.add('journey-card');
            if (index % 2 === 0) {
                journeyCard.classList.add('left');
            } else {
                journeyCard.classList.add('right');
            }

            const timelineContent = document.createElement('div');
            timelineContent.classList.add('timeline-content');
            const year = document.createElement('h4');
            year.textContent = item.year;
            const title = document.createElement('h5');
            title.textContent = item.title;
            const description = document.createElement('p');
            description.textContent = item.description;

            timelineContent.appendChild(year);
            timelineContent.appendChild(title);
            timelineContent.appendChild(description);

            const timelineIcon = document.createElement('div');
            timelineIcon.classList.add('timeline-icon');
            const icon = document.createElement('i');
            icon.classList.add(...item.iconClass.split(' '));
            timelineIcon.appendChild(icon);

            journeyCard.appendChild(timelineContent);
            journeyCard.appendChild(timelineIcon);

            timelineContainer.appendChild(journeyCard);
        });
    }
}

// Main DOMContentLoaded Listener
document.addEventListener('DOMContentLoaded', () => {
    // Observe skill levels for animation
    document.querySelectorAll('.skill-level').forEach(skill => {
        contentObserver.observe(skill);
    });

    // Render journey timeline cards
    renderJourneyTimelineCards();

    // Mobile Navigation Toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.nav')) {
                navLinks.classList.remove('active');
            }
        });
    }

    // Smooth Scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Close mobile menu after clicking a link
                if (navLinks && navLinks.classList.contains('active')) {
                    navLinks.classList.remove('active');
                }
            }
        });
    });

    // Observe animated elements
    document.querySelectorAll('.fade-in-element, .animated-section, .fade-in-up, .fade-in-left, .fade-in-right').forEach(element => {
        contentObserver.observe(element);
    });

    // Project Filtering
    const filterButtons = document.querySelectorAll('.filter-btn');
    const projectCards = document.querySelectorAll('.project-card');

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            filterButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const filter = button.dataset.filter;

            projectCards.forEach(card => {
                if (filter === 'all' || card.dataset.category === filter) {
                    card.style.display = 'block';
                    setTimeout(() => card.classList.add('animate'), 100);
                } else {
                    card.style.display = 'none';
                    card.classList.remove('animate');
                }
            });
        });
    });

    // FAQ Accordion
    const faqQuestions = document.querySelectorAll('.faq-question');

    faqQuestions.forEach(question => {
        question.addEventListener('click', () => {
            const answer = question.nextElementSibling;
            const isOpen = question.classList.contains('active');

            faqQuestions.forEach(q => {
                if (q !== question) {
                    q.classList.remove('active');
                    q.nextElementSibling.style.maxHeight = null;
                }
            });

            question.classList.toggle('active');
            if (!isOpen) {
                answer.style.maxHeight = answer.scrollHeight + 'px';
            } else {
                answer.style.maxHeight = null;
            }
        });
    });

    // Contact Form Submission (requires backend for full functionality)
    const contactForm = document.querySelector('.contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Thank you for your message! I will get back to you soon.');
            contactForm.reset();
        });
    }
}); 