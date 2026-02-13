/**
 * SupportForm Component
 * A fully responsive, accessible support form with validation and submission handling
 */

import React, { useState } from 'react';

const SupportForm = ({ apiEndpoint = '/api/support/submit', onSuccess, theme = 'light' }) => {
  // Define initial form state
  const initialFormData = {
    name: '',
    email: '',
    subject: '',
    category: 'general',
    priority: 'medium',
    message: ''
  };

  // Component state
  const [formData, setFormData] = useState(initialFormData);
  const [status, setStatus] = useState('idle'); // idle, submitting, success, error
  const [ticketId, setTicketId] = useState(null);
  const [error, setError] = useState(null);
  const [errors, setErrors] = useState({});

  // Validation rules
  const validateField = (name, value) => {
    switch (name) {
      case 'name':
        if (value.length < 2) return 'Name must be at least 2 characters';
        if (value.length > 255) return 'Name must be less than 255 characters';
        return '';
      case 'email':
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!value) return 'Email is required';
        if (!emailRegex.test(value)) return 'Please enter a valid email address';
        return '';
      case 'subject':
        if (value.length < 5) return 'Subject must be at least 5 characters';
        if (value.length > 200) return 'Subject must be less than 200 characters';
        return '';
      case 'message':
        if (value.length < 10) return 'Message must be at least 10 characters';
        if (value.length > 5000) return 'Message must be less than 5000 characters';
        return '';
      default:
        return '';
    }
  };

  // Validate entire form
  const validateForm = () => {
    const newErrors = {};
    let isValid = true;

    Object.entries(formData).forEach(([key, value]) => {
      const fieldError = validateField(key, value);
      if (fieldError) {
        newErrors[key] = fieldError;
        isValid = false;
      }
    });

    setErrors(newErrors);
    return isValid;
  };

  // Handle input changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate form
    if (!validateForm()) {
      // Focus on first error field
      const firstErrorField = Object.keys(errors)[0];
      if (firstErrorField) {
        const element = document.querySelector(`[name="${firstErrorField}"]`);
        if (element) element.focus();
      }
      return;
    }

    // Set submitting state
    setStatus('submitting');
    setError(null);

    try {
      // Submit form data
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Submission failed');
      }

      const result = await response.json();
      setTicketId(result.ticketId || 'N/A');
      setStatus('success');

      // Call success callback if provided
      if (onSuccess && typeof onSuccess === 'function') {
        onSuccess(result.ticketId || 'N/A');
      }
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  // Reset form for new submission
  const resetForm = () => {
    setFormData(initialFormData);
    setStatus('idle');
    setTicketId(null);
    setError(null);
    setErrors({});
  };

  // Render form based on current status
  if (status === 'success') {
    return (
      <div className={`max-w-2xl mx-auto p-6 rounded-lg shadow-md ${
        theme === 'dark' ? 'bg-gray-800 text-white' : 'bg-white'
      }`}>
        <div className="flex flex-col items-center text-center">
          {/* Success icon */}
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          
          <h2 className="text-2xl font-bold mb-2">Thank You!</h2>
          <p className="mb-4">Your support request has been submitted successfully.</p>
          
          <div className={`bg-green-50 rounded-lg p-4 w-full max-w-md mb-4 ${
            theme === 'dark' ? 'bg-gray-700' : ''
          }`}>
            <p className="text-sm font-medium mb-1">Ticket ID:</p>
            <p className="font-mono text-lg font-bold">{ticketId}</p>
          </div>
          
          <p className="mb-6">Our AI assistant will respond to your email within 5 minutes.</p>
          
          <button
            onClick={resetForm}
            className="py-2 px-6 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label="Submit another request"
          >
            Submit Another Request
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`max-w-2xl mx-auto p-6 rounded-lg shadow-md ${
      theme === 'dark' ? 'bg-gray-800 text-white' : 'bg-white'
    }`}>
      <h2 className="text-xl font-bold mb-6">Contact Support</h2>
      
      {status === 'error' && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg" role="alert">
          <p>{error || 'An error occurred while submitting your request.'}</p>
        </div>
      )}
      
      <form onSubmit={handleSubmit} noValidate>
        {/* Name Field */}
        <div className="mb-4">
          <label htmlFor="name" className="block text-sm font-medium mb-1">
            Name *
          </label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            onBlur={() => {
              const error = validateField('name', formData.name);
              setErrors(prev => ({ ...prev, name: error }));
            }}
            placeholder="John Doe"
            className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.name ? 'border-red-500' : 'border-gray-300'
            } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
            aria-invalid={!!errors.name}
            aria-describedby={errors.name ? 'name-error' : undefined}
            disabled={status === 'submitting'}
          />
          {errors.name && (
            <p id="name-error" className="mt-1 text-sm text-red-600">
              {errors.name}
            </p>
          )}
        </div>
        
        {/* Email Field */}
        <div className="mb-4">
          <label htmlFor="email" className="block text-sm font-medium mb-1">
            Email *
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            onBlur={() => {
              const error = validateField('email', formData.email);
              setErrors(prev => ({ ...prev, email: error }));
            }}
            placeholder="john@example.com"
            className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.email ? 'border-red-500' : 'border-gray-300'
            } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'email-error' : undefined}
            disabled={status === 'submitting'}
          />
          {errors.email && (
            <p id="email-error" className="mt-1 text-sm text-red-600">
              {errors.email}
            </p>
          )}
        </div>
        
        {/* Subject Field */}
        <div className="mb-4">
          <label htmlFor="subject" className="block text-sm font-medium mb-1">
            Subject *
          </label>
          <input
            type="text"
            id="subject"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            onBlur={() => {
              const error = validateField('subject', formData.subject);
              setErrors(prev => ({ ...prev, subject: error }));
            }}
            placeholder="Brief description of your issue"
            className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.subject ? 'border-red-500' : 'border-gray-300'
            } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
            aria-invalid={!!errors.subject}
            aria-describedby={errors.subject ? 'subject-error' : undefined}
            disabled={status === 'submitting'}
          />
          {errors.subject && (
            <p id="subject-error" className="mt-1 text-sm text-red-600">
              {errors.subject}
            </p>
          )}
        </div>
        
        {/* Category and Priority Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label htmlFor="category" className="block text-sm font-medium mb-1">
              Category *
            </label>
            <select
              id="category"
              name="category"
              value={formData.category}
              onChange={handleChange}
              className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.category ? 'border-red-500' : 'border-gray-300'
              } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
              disabled={status === 'submitting'}
            >
              <option value="general">General Question</option>
              <option value="technical">Technical Support</option>
              <option value="billing">Billing Inquiry</option>
              <option value="bug_report">Bug Report</option>
              <option value="feedback">Feedback</option>
            </select>
          </div>
          
          <div>
            <label htmlFor="priority" className="block text-sm font-medium mb-1">
              Priority
            </label>
            <select
              id="priority"
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.priority ? 'border-red-500' : 'border-gray-300'
              } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
              disabled={status === 'submitting'}
            >
              <option value="low">Low - Not urgent</option>
              <option value="medium">Medium - Need help soon</option>
              <option value="high">High - Urgent issue</option>
            </select>
          </div>
        </div>
        
        {/* Message Field */}
        <div className="mb-4">
          <label htmlFor="message" className="block text-sm font-medium mb-1">
            Message *
          </label>
          <textarea
            id="message"
            name="message"
            value={formData.message}
            onChange={handleChange}
            onBlur={() => {
              const error = validateField('message', formData.message);
              setErrors(prev => ({ ...prev, message: error }));
            }}
            rows="6"
            placeholder="Please describe your issue in detail..."
            className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none ${
              errors.message ? 'border-red-500' : 'border-gray-300'
            } ${theme === 'dark' ? 'bg-gray-700' : ''}`}
            aria-invalid={!!errors.message}
            aria-describedby={errors.message ? 'message-error' : 'message-counter'}
            disabled={status === 'submitting'}
          />
          <div className="flex justify-between mt-1">
            <div>
              {errors.message && (
                <p id="message-error" className="text-sm text-red-600">
                  {errors.message}
                </p>
              )}
            </div>
            <div id="message-counter" className="text-sm text-gray-500">
              {formData.message.length}/5000
            </div>
          </div>
        </div>
        
        {/* Submit Button */}
        <button
          type="submit"
          disabled={status === 'submitting'}
          className={`w-full py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 ${
            status === 'submitting'
              ? 'bg-blue-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
          } text-white`}
          aria-busy={status === 'submitting'}
        >
          {status === 'submitting' ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Submitting...
            </span>
          ) : (
            'Submit Request'
          )}
        </button>
      </form>
    </div>
  );
};

export default SupportForm;