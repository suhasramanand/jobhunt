import React from 'react';
import { Clock, List, FileText, X } from 'lucide-react';
import { Button } from './ui/button';

const Sidebar = ({ isOpen, onClose, activeView, onViewChange }) => {
  const menuItems = [
    {
      id: 'all-jobs',
      label: 'All Jobs',
      icon: <List className="h-4 w-4" />,
      description: 'All jobs since it fetched'
    },
    {
      id: 'recent-jobs',
      label: 'Recent Jobs',
      icon: <Clock className="h-4 w-4" />,
      description: 'Jobs posted in the last hour'
    },
    {
      id: 'my-applications',
      label: 'My Applications',
      icon: <FileText className="h-4 w-4" />,
      description: 'Track your applications'
    }
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed top-0 left-0 h-full w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out z-50 lg:translate-x-0 lg:static lg:shadow-none
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Navigation</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="lg:hidden"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Menu Items */}
        <nav className="p-4 space-y-2">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`
                w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-left transition-colors duration-200
                ${activeView === item.id 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200' 
                  : 'text-gray-700 hover:bg-gray-100'
                }
              `}
            >
              {item.icon}
              <div className="flex-1">
                <div className="font-medium">{item.label}</div>
                <div className="text-xs text-gray-500">{item.description}</div>
              </div>
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="absolute bottom-4 left-4 right-4">
          <div className="text-xs text-gray-500 text-center">
            <p>Job data updates every 2 hours</p>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
