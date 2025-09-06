/**
 * ToneBridge Survey Forms Handler
 * Manages form validation and submission
 */

document.addEventListener('DOMContentLoaded', function() {
    const surveyForm = document.getElementById('surveyForm');
    const thankYouMessage = document.getElementById('thankYouMessage');
    
    if (!surveyForm) return;
    
    // Form validation
    surveyForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!surveyForm.checkValidity()) {
            e.stopPropagation();
            surveyForm.classList.add('was-validated');
            return;
        }
        
        try {
            // Collect form data
            const formData = new FormData(surveyForm);
            const surveyData = {};
            
            // Process all form fields
            for (let [key, value] of formData.entries()) {
                if (surveyData[key]) {
                    // Handle multiple values (checkboxes)
                    if (Array.isArray(surveyData[key])) {
                        surveyData[key].push(value);
                    } else {
                        surveyData[key] = [surveyData[key], value];
                    }
                } else {
                    surveyData[key] = value;
                }
            }
            
            // Add metadata
            surveyData.submitted_at = new Date().toISOString();
            surveyData.user_agent = navigator.userAgent;
            surveyData.language = navigator.language;
            
            // Submit to backend
            const response = await fetch('/api/save_survey', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(surveyData)
            });
            
            if (response.ok) {
                // Hide form and show thank you message
                surveyForm.style.display = 'none';
                thankYouMessage.classList.remove('d-none');
                
                // Scroll to top
                window.scrollTo({top: 0, behavior: 'smooth'});
                
                console.log('Survey submitted successfully');
            } else {
                throw new Error('서버 오류가 발생했습니다.');
            }
            
        } catch (error) {
            console.error('Survey submission error:', error);
            alert('설문 제출 중 오류가 발생했습니다. 다시 시도해 주세요.');
        }
    });
    
    // Range input value display
    const rangeInputs = document.querySelectorAll('input[type="range"]');
    rangeInputs.forEach(input => {
        const valueDisplay = document.createElement('div');
        valueDisplay.className = 'text-center mt-1 small text-muted';
        valueDisplay.textContent = `현재 값: ${input.value}`;
        input.parentNode.appendChild(valueDisplay);
        
        input.addEventListener('input', function() {
            valueDisplay.textContent = `현재 값: ${this.value}`;
        });
    });
    
    // Checkbox limit validation for improvement areas
    const improvementCheckboxes = document.querySelectorAll('input[name="improvement_areas"]');
    improvementCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const checked = document.querySelectorAll('input[name="improvement_areas"]:checked');
            if (checked.length > 3) {
                this.checked = false;
                alert('최대 3개까지만 선택할 수 있습니다.');
            }
        });
    });
    
    // Conditional field visibility
    const hearingLossTime = document.querySelectorAll('input[name="hearing_loss_time"]');
    const lossAgeField = document.getElementById('loss_age');
    
    hearingLossTime.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'postlingual') {
                lossAgeField.required = true;
                lossAgeField.parentNode.style.display = 'block';
            } else {
                lossAgeField.required = false;
                lossAgeField.parentNode.style.display = 'none';
            }
        });
    });
    
    // Korean background conditional
    const koreanBackground = document.querySelectorAll('input[name="korean_background"]');
    koreanBackground.forEach(radio => {
        radio.addEventListener('change', function() {
            // Could add L2 specific fields here if needed
            console.log('Korean background changed to:', this.value);
        });
    });
    
    // Auto-save draft (optional)
    let autoSaveTimer;
    surveyForm.addEventListener('input', function() {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            saveDraft();
        }, 2000);
    });
    
    function saveDraft() {
        try {
            const formData = new FormData(surveyForm);
            const draftData = {};
            
            for (let [key, value] of formData.entries()) {
                draftData[key] = value;
            }
            
            localStorage.setItem('tonebridge_survey_draft', JSON.stringify(draftData));
            console.log('Draft saved');
        } catch (e) {
            console.warn('Could not save draft:', e);
        }
    }
    
    // Load draft on page load
    function loadDraft() {
        try {
            const draft = localStorage.getItem('tonebridge_survey_draft');
            if (draft) {
                const draftData = JSON.parse(draft);
                
                Object.keys(draftData).forEach(key => {
                    const element = document.querySelector(`[name="${key}"]`);
                    if (element) {
                        if (element.type === 'checkbox' || element.type === 'radio') {
                            if (element.value === draftData[key]) {
                                element.checked = true;
                            }
                        } else {
                            element.value = draftData[key];
                        }
                    }
                });
                
                console.log('Draft loaded');
            }
        } catch (e) {
            console.warn('Could not load draft:', e);
        }
    }
    
    // Load draft on initialization
    loadDraft();
    
    // Clear draft after successful submission
    surveyForm.addEventListener('submit', function() {
        localStorage.removeItem('tonebridge_survey_draft');
    });
});

// Google Forms integration helper
function generateGoogleFormUrl(surveyData) {
    // This would map survey data to Google Forms URL parameters
    // Implementation depends on the actual Google Form structure
    const baseUrl = 'https://docs.google.com/forms/d/e/YOUR_FORM_ID/formResponse';
    const params = new URLSearchParams();
    
    // Map survey data to Google Forms entry IDs
    // Example: params.append('entry.123456789', surveyData.hearing_loss_time);
    
    return `${baseUrl}?${params.toString()}`;
}

// Export survey data as CSV (for admin/research purposes)
function exportSurveyData() {
    // This would be called from an admin interface
    fetch('/api/export_surveys')
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'tonebridge_survey_data.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            console.error('Export error:', error);
            alert('데이터 내보내기 중 오류가 발생했습니다.');
        });
}
