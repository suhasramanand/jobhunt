import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { Search, Filter, ExternalLink, MapPin, Building2, Clock, Users, Globe, Menu, CheckCircle, XCircle } from 'lucide-react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { Switch } from './components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import Sidebar from './components/Sidebar';
import ApplicationModal from './components/ApplicationModal';
import { useApplications } from './hooks/useApplications';

const ROLES = ['All', 'SDE', 'SWE', 'DevOps', 'Cloud', 'AI/ML'];

function App() {
  const [jobs, setJobs] = useState([]);
  const [filteredJobs, setFilteredJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRole, setSelectedRole] = useState('All');
  const [visaSponsorshipOnly, setVisaSponsorshipOnly] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeView, setActiveView] = useState('all-jobs');
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  
  const { addApplication, getApplicationStatus, getAppliedJobs } = useApplications();

  // Load jobs data from GitHub repo
  useEffect(() => {
    const loadJobs = async () => {
      try {
        setLoading(true);
        // Fetch the CSV file from the GitHub repo
        const response = await fetch('https://raw.githubusercontent.com/suhasramanand/jobhunt/main/data/jobs.csv');
        
        if (!response.ok) {
          throw new Error(`Failed to fetch jobs: ${response.status}`);
        }
        
        const csvText = await response.text();
        
        Papa.parse(csvText, {
          header: true,
          complete: (results) => {
            setJobs(results.data.filter(job => job.id)); // Filter out empty rows
            setLoading(false);
          },
          error: (error) => {
            console.error('CSV parsing error:', error);
            setError('Failed to parse jobs data');
            setLoading(false);
          }
        });
      } catch (err) {
        console.error('Error loading jobs:', err);
        setError('Failed to load jobs data');
        setLoading(false);
      }
    };

    loadJobs();
  }, []);

  // Filter jobs based on view, search term, role, and visa sponsorship
  useEffect(() => {
    let filtered = jobs;

    // Filter by view type
    if (activeView === 'recent-jobs') {
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
      filtered = filtered.filter(job => {
        try {
          const jobDate = new Date(job.posted_at || job.scraped_at);
          return jobDate >= oneHourAgo;
        } catch (error) {
          return false;
        }
      });
    } else if (activeView === 'my-applications') {
      const appliedJobIds = getAppliedJobs().map(app => app.jobId);
      filtered = filtered.filter(job => appliedJobIds.includes(job.id));
    }

    // Filter by search term (company or title)
    if (searchTerm) {
      filtered = filtered.filter(job => 
        job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.company.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Filter by role
    if (selectedRole !== 'All') {
      filtered = filtered.filter(job => job.role === selectedRole);
    }

    // Filter by visa sponsorship
    if (visaSponsorshipOnly) {
      filtered = filtered.filter(job => job.visa_sponsorship === 'True' || job.visa_sponsorship === true);
    }

    setFilteredJobs(filtered);
  }, [jobs, activeView, searchTerm, selectedRole, visaSponsorshipOnly, getAppliedJobs]);

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (error) {
      return dateString;
    }
  };

  const getRoleColor = (role) => {
    const colors = {
      'SDE': 'bg-blue-100 text-blue-800',
      'SWE': 'bg-green-100 text-green-800',
      'DevOps': 'bg-purple-100 text-purple-800',
      'Cloud': 'bg-orange-100 text-orange-800',
      'AI/ML': 'bg-pink-100 text-pink-800'
    };
    return colors[role] || 'bg-gray-100 text-gray-800';
  };

  const handleApplyClick = (job) => {
    setSelectedJob(job);
    setModalOpen(true);
  };

  const handleApplicationConfirm = (job, applied) => {
    addApplication(job, applied);
  };

  const getApplicationStatusIcon = (jobId) => {
    const status = getApplicationStatus(jobId);
    if (status === 'applied') {
      return <CheckCircle className="h-4 w-4 text-green-600" />;
    } else if (status === 'not_applied') {
      return <XCircle className="h-4 w-4 text-red-600" />;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading jobs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-96">
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => window.location.reload()} className="w-full">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="flex">
        {/* Sidebar */}
        <Sidebar 
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          activeView={activeView}
          onViewChange={setActiveView}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-h-screen">
          {/* Header */}
          <header className="bg-white shadow-sm border-b">
            <div className="px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center h-16">
                <div className="flex items-center space-x-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSidebarOpen(!sidebarOpen)}
                    className="lg:hidden"
                  >
                    <Menu className="h-5 w-5" />
                  </Button>
                  <Users className="h-8 w-8 text-blue-600" />
                  <h1 className="text-2xl font-bold text-gray-900">Job Aggregator</h1>
                </div>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <Clock className="h-4 w-4" />
                  <span>Updated every 2 hours</span>
                </div>
              </div>
            </div>
          </header>

          {/* Main content */}
          <div className="flex-1 px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Filter className="h-5 w-5" />
              <span>Filters</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Search */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Search</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Company or job title..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>

              {/* Role Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Role</label>
                <Select value={selectedRole} onValueChange={setSelectedRole}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map(role => (
                      <SelectItem key={role} value={role}>{role}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Visa Sponsorship Toggle */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Visa Sponsorship</label>
                <div className="flex items-center space-x-3 pt-2">
                  <Switch
                    id="visa-sponsorship"
                    checked={visaSponsorshipOnly}
                    onCheckedChange={setVisaSponsorshipOnly}
                  />
                  <label htmlFor="visa-sponsorship" className="text-sm text-gray-600">
                    Show only jobs with visa sponsorship
                  </label>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Summary */}
        <div className="mb-6">
          <p className="text-gray-600">
            Showing <span className="font-semibold">{filteredJobs.length}</span> jobs
            {searchTerm && ` matching "${searchTerm}"`}
            {selectedRole !== 'All' && ` for ${selectedRole} roles`}
            {visaSponsorshipOnly && ' with visa sponsorship'}
          </p>
        </div>

        {/* Jobs Grid */}
        {filteredJobs.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No jobs found</h3>
              <p className="text-gray-500">Try adjusting your filters or search terms.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredJobs.map((job) => (
              <Card key={job.id} className="hover:shadow-lg transition-shadow duration-200">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <CardTitle className="text-lg leading-tight mb-2">
                        {job.title}
                      </CardTitle>
                      <div className="flex items-center space-x-2 text-sm text-gray-600 mb-2">
                        <Building2 className="h-4 w-4" />
                        <span>{job.company}</span>
                      </div>
                      <div className="flex items-center space-x-2 text-sm text-gray-600">
                        <MapPin className="h-4 w-4" />
                        <span>{job.location}</span>
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getRoleColor(job.role)}`}>
                      {job.role}
                    </span>
                  </div>
                </CardHeader>
                
                <CardContent className="pt-0">
                  <p className="text-sm text-gray-600 mb-4 line-clamp-3">
                    {job.snippet}
                  </p>
                  
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
                    <span>Posted: {formatDate(job.posted_at)}</span>
                    {job.visa_sponsorship === 'True' || job.visa_sponsorship === true ? (
                      <span className="flex items-center space-x-1 text-green-600">
                        <Globe className="h-3 w-3" />
                        <span>Visa Sponsorship</span>
                      </span>
                    ) : (
                      <span className="text-gray-400">No sponsorship info</span>
                    )}
                  </div>
                  
                  <div className="flex space-x-2">
                    {job.post_url && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => window.open(job.post_url, '_blank')}
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        View Job
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleApplyClick(job)}
                      className="px-3"
                    >
                      {getApplicationStatusIcon(job.id) || 'Apply'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

            {/* Footer */}
            <footer className="mt-12 pt-8 border-t border-gray-200">
              <div className="text-center text-sm text-gray-500">
                <p>Job data is automatically updated every 2 hours via GitHub Actions</p>
                <p className="mt-1">
                  Last updated: {jobs.length > 0 ? formatDate(jobs[0]?.scraped_at) : 'Unknown'}
                </p>
              </div>
            </footer>
          </div>
        </div>
      </div>

      {/* Application Modal */}
      <ApplicationModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        job={selectedJob}
        onConfirm={handleApplicationConfirm}
      />
    </div>
  );
}

export default App;
