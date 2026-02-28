'use client';

import { useState } from 'react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'upload' | 'github'>('upload');
  const [fileName, setFileName] = useState<string>('');
  const [githubUrl, setGithubUrl] = useState<string>('');

  const handleZipSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFileName(e.target.files[0].name);
    }
  };

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Upload submitted for:', fileName);
    // Mock - does nothing yet
  };

  const handleGithubSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('GitHub submitted for:', githubUrl);
    // Mock - does nothing yet
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Code Quality Analyzer</h1>
          <p className="text-gray-600">Upload your project and get AI-powered improvements</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-lg shadow-lg p-8">
          {/* Tabs */}
          <div className="flex gap-4 mb-8 border-b">
            <button
              onClick={() => setActiveTab('upload')}
              className={`pb-4 px-4 font-semibold transition-colors ${
                activeTab === 'upload'
                  ? 'text-indigo-600 border-b-2 border-indigo-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Upload ZIP
            </button>
            <button
              onClick={() => setActiveTab('github')}
              className={`pb-4 px-4 font-semibold transition-colors ${
                activeTab === 'github'
                  ? 'text-indigo-600 border-b-2 border-indigo-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              GitHub Link
            </button>
          </div>

          {/* Upload Tab */}
          {activeTab === 'upload' && (
            <form onSubmit={handleUploadSubmit}>
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-4">
                  Select your project ZIP
                </label>
                <div className="border-2 border-dashed border-indigo-300 rounded-lg p-8 text-center hover:border-indigo-500 transition-colors cursor-pointer"
                  onClick={() => document.getElementById('zip-input')?.click()}
                >
                  <svg className="w-12 h-12 mx-auto mb-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-gray-600 font-medium">
                    {fileName ? fileName : 'Click to select ZIP file or drag and drop'}
                  </p>
                </div>
                <input
                  id="zip-input"
                  type="file"
                  accept=".zip"
                  onChange={handleZipSelect}
                  className="hidden"
                />
              </div>
              <button
                type="submit"
                disabled={!fileName}
                className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                  fileName
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                Analyze Project
              </button>
            </form>
          )}

          {/* GitHub Tab */}
          {activeTab === 'github' && (
            <form onSubmit={handleGithubSubmit}>
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  GitHub Repository URL
                </label>
                <input
                  type="url"
                  placeholder="https://github.com/username/repo"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
                />
                <p className="text-xs text-gray-500 mt-2">Supports public repositories (private support coming soon)</p>
              </div>
              <button
                type="submit"
                disabled={!githubUrl}
                className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                  githubUrl
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                Analyze Repository
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
