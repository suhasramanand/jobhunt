import React, { useState } from 'react';
import { X, Check, XCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

const ApplicationModal = ({ isOpen, onClose, job, onConfirm }) => {
  const [applied, setApplied] = useState(null);

  const handleConfirm = () => {
    onConfirm(job, applied);
    setApplied(null);
    onClose();
  };

  const handleCancel = () => {
    setApplied(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg font-semibold">Application Status</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCancel}
          >
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <h3 className="font-medium text-gray-900">{job.title}</h3>
            <p className="text-sm text-gray-600">{job.company}</p>
          </div>
          
          <div className="space-y-3">
            <p className="text-sm text-gray-700">Did you apply to this job?</p>
            
            <div className="flex space-x-3">
              <Button
                variant={applied === true ? "default" : "outline"}
                size="sm"
                onClick={() => setApplied(true)}
                className="flex-1"
              >
                <Check className="h-4 w-4 mr-2" />
                Yes, I applied
              </Button>
              
              <Button
                variant={applied === false ? "destructive" : "outline"}
                size="sm"
                onClick={() => setApplied(false)}
                className="flex-1"
              >
                <XCircle className="h-4 w-4 mr-2" />
                No, I didn't apply
              </Button>
            </div>
          </div>
          
          <div className="flex space-x-3 pt-4">
            <Button
              variant="outline"
              onClick={handleCancel}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={applied === null}
              className="flex-1"
            >
              Confirm
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ApplicationModal;
