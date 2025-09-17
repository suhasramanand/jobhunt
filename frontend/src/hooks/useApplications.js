import { useState, useEffect } from 'react';

const APPLICATIONS_KEY = 'jobhunt_applications';

export const useApplications = () => {
  const [applications, setApplications] = useState([]);

  // Load applications from localStorage on mount
  useEffect(() => {
    try {
      const savedApplications = localStorage.getItem(APPLICATIONS_KEY);
      if (savedApplications) {
        setApplications(JSON.parse(savedApplications));
      }
    } catch (error) {
      console.error('Error loading applications from localStorage:', error);
    }
  }, []);

  // Save applications to localStorage whenever applications change
  useEffect(() => {
    try {
      localStorage.setItem(APPLICATIONS_KEY, JSON.stringify(applications));
    } catch (error) {
      console.error('Error saving applications to localStorage:', error);
    }
  }, [applications]);

  const addApplication = (job, applied) => {
    const application = {
      id: job.id,
      jobId: job.id,
      title: job.title,
      company: job.company,
      location: job.location,
      role: job.role,
      postUrl: job.post_url,
      applied: applied,
      appliedAt: new Date().toISOString(),
      status: applied ? 'applied' : 'not_applied'
    };

    setApplications(prev => {
      // Remove any existing application for this job
      const filtered = prev.filter(app => app.jobId !== job.id);
      return [...filtered, application];
    });
  };

  const getApplicationStatus = (jobId) => {
    const application = applications.find(app => app.jobId === jobId);
    return application ? application.status : null;
  };

  const getAppliedJobs = () => {
    return applications.filter(app => app.applied === true);
  };

  const getNotAppliedJobs = () => {
    return applications.filter(app => app.applied === false);
  };

  const removeApplication = (jobId) => {
    setApplications(prev => prev.filter(app => app.jobId !== jobId));
  };

  return {
    applications,
    addApplication,
    getApplicationStatus,
    getAppliedJobs,
    getNotAppliedJobs,
    removeApplication
  };
};
