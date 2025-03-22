// main.js - Custom JavaScript for the Financial Analysis App

document.addEventListener('DOMContentLoaded', function() {
    // Company search functionality with form submission
    const companySearchForm = document.querySelector('form[action="/company_analysis"]');
    if (companySearchForm) {
        const companySearchInput = companySearchForm.querySelector('#companySearch');
        if (companySearchInput) {
            companySearchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const companyCode = this.value.trim().toUpperCase();
                    if (companyCode) {
                        companySearchForm.submit();
                    }
                }
            });
        }
    }

    // Handle company search on company_analysis.html page
    const companySearchFormAnalysis = document.getElementById('companySearchForm');
    if (companySearchFormAnalysis) {
        companySearchFormAnalysis.addEventListener('submit', function(e) {
            const companyCode = this.querySelector('input[name="code"]').value.trim();
            if (!companyCode) {
                e.preventDefault();
                alert('Vui lòng nhập mã cổ phiếu để tìm kiếm');
            }
        });
    }

    // Sector select functionality on sector_analysis.html page
    const sectorSelectForm = document.getElementById('sectorSelectForm');
    if (sectorSelectForm) {
        const sectorSelect = sectorSelectForm.querySelector('#sectorSelect');
        if (sectorSelect) {
            sectorSelect.addEventListener('change', function() {
                const selectedSector = this.value;
                if (selectedSector && selectedSector !== 'Chọn ngành...') {
                    // You could auto-submit the form on change, but we'll keep the button for UX
                    // sectorSelectForm.submit();
                }
            });
        }
    }

    // Comparison page functionality
    // Toggle additional company input
    const addCompanyCheckbox = document.getElementById('addCompany');
    if (addCompanyCheckbox) {
        addCompanyCheckbox.addEventListener('change', function() {
            const company3Row = document.querySelector('.company3-row');
            if (company3Row) {
                company3Row.classList.toggle('d-none', !this.checked);
            }
        });
    }

    // Toggle additional sector input
    const addSectorCheckbox = document.getElementById('addSector');
    if (addSectorCheckbox) {
        addSectorCheckbox.addEventListener('change', function() {
            const sector3Row = document.querySelector('.sector3-row');
            if (sector3Row) {
                sector3Row.classList.toggle('d-none', !this.checked);
            }
        });
    }

    // Handle comparison form validations
    const companiesComparisonForm = document.getElementById('companiesComparisonForm');
    if (companiesComparisonForm) {
        companiesComparisonForm.addEventListener('submit', function(e) {
            const company1 = this.querySelector('#company1').value.trim();
            const company2 = this.querySelector('#company2').value.trim();
            
            if (!company1 || !company2) {
                e.preventDefault();
                alert('Vui lòng nhập cả hai mã cổ phiếu để so sánh');
            }
        });
    }

    const sectorsComparisonForm = document.getElementById('sectorsComparisonForm');
    if (sectorsComparisonForm) {
        sectorsComparisonForm.addEventListener('submit', function(e) {
            const sector1 = this.querySelector('#sector1').value;
            const sector2 = this.querySelector('#sector2').value;
            
            if (!sector1 || !sector2) {
                e.preventDefault();
                alert('Vui lòng chọn cả hai ngành để so sánh');
            }
        });
    }

    const companyWithSectorForm = document.getElementById('companyWithSectorForm');
    if (companyWithSectorForm) {
        companyWithSectorForm.addEventListener('submit', function(e) {
            const company = this.querySelector('#company').value.trim();
            const sector = this.querySelector('#sector').value;
            
            if (!company || !sector) {
                e.preventDefault();
                alert('Vui lòng nhập mã cổ phiếu và chọn ngành để so sánh');
            }
        });
    }

    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Add animation to the dashboard cards
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.05)';
        });
    });

    // Active tab handling for comparison page
    const urlParams = new URLSearchParams(window.location.search);
    const comparisonType = urlParams.get('type');
    
    if (comparisonType) {
        let tabId;
        
        if (comparisonType === 'companies') {
            tabId = 'companies-tab';
        } else if (comparisonType === 'sectors') {
            tabId = 'sectors-tab';
        } else if (comparisonType === 'company_with_sector') {
            tabId = 'company-with-sector-tab';
        }
        
        if (tabId) {
            const tabElement = document.getElementById(tabId);
            if (tabElement) {
                const tab = new bootstrap.Tab(tabElement);
                tab.show();
            }
        }
    }
});