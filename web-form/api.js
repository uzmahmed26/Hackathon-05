/**
 * API Client Functions for Support Form
 * Handles communication with the backend API
 */

/**
 * Submits the support form data to the backend
 * @param {Object} formData - The form data to submit
 * @returns {Promise<Object>} - The response from the API
 */
export async function submitSupportForm(formData) {
  const response = await fetch('/api/support/submit', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json' 
    },
    body: JSON.stringify(formData)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Submission failed');
  }
  
  return await response.json();
}

/**
 * Retrieves the status of a support ticket
 * @param {string} ticketId - The ID of the ticket to check
 * @returns {Promise<Object>} - The ticket status information
 */
export async function getTicketStatus(ticketId) {
  const response = await fetch(`/api/support/ticket/${ticketId}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch ticket status');
  }
  
  return await response.json();
}