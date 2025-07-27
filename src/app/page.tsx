'use client';

import { useState } from 'react';
import Image from 'next/image';

interface ChatbotState {
  isOpen: boolean;
  showDetails: boolean;
}

export default function Home() {
  const [formData, setFormData] = useState({
    scrapeSite: '',
    productName: '',
    outputFolder: '',
    recipientEmail: ''
  });

  const [chatbot, setChatbot] = useState<ChatbotState>({
    isOpen: false,
    showDetails: false
  });

  const [isProcessing, setIsProcessing] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleStart = () => {
    if (!formData.scrapeSite || !formData.productName || !formData.outputFolder || !formData.recipientEmail) {
      alert('Please fill in all fields');
      return;
    }
    setIsProcessing(true);
    // Simulate processing
    setTimeout(() => {
      setIsProcessing(false);
      alert('Scraping process started! You will receive an email notification when complete.');
    }, 2000);
  };

  const toggleChatbot = () => {
    setChatbot({ ...chatbot, isOpen: !chatbot.isOpen });
  };

  const showDetails = () => {
    setChatbot({ ...chatbot, showDetails: true });
  };

  const backToMain = () => {
    setChatbot({ ...chatbot, showDetails: false });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-red-900 relative overflow-hidden">
      {/* Animated background particles */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full">
          <div className="animate-spin-slow w-96 h-96 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-3xl"></div>
        </div>
        <div className="absolute -bottom-1/2 -right-1/2 w-full h-full">
          <div className="animate-pulse w-96 h-96 bg-gradient-to-r from-red-500/20 to-pink-500/20 rounded-full blur-3xl"></div>
        </div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-6 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-6xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-red-400 bg-clip-text text-transparent mb-4 animate-pulse">
            Agentic AI
          </h1>
          <div className="w-32 h-1 bg-gradient-to-r from-blue-500 to-red-500 mx-auto rounded-full"></div>
        </div>

        {/* Main Form */}
        <div className="max-w-2xl mx-auto">
          <div className="bg-white/10 backdrop-blur-lg rounded-3xl p-8 shadow-2xl border border-white/20">
            <div className="space-y-6">
              {/* Scraping Site Dropdown */}
              <div className="group">
                <label className="block text-white text-sm font-medium mb-2 group-hover:text-blue-300 transition-colors">
                  From which site do you want to scrape?
                </label>
                <select
                  name="scrapeSite"
                  value={formData.scrapeSite}
                  onChange={handleInputChange}
                  className="w-full p-4 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-300 hover:bg-white/30"
                >
                  <option value="" className="text-gray-800">Select a platform</option>
                  <option value="flipkart" className="text-gray-800">Flipkart</option>
                  <option value="amazon" className="text-gray-800">Amazon</option>
                  <option value="bigbasket" className="text-gray-800">Big Basket</option>
                </select>
              </div>

              {/* Product Name Input */}
              <div className="group">
                <label className="block text-white text-sm font-medium mb-2 group-hover:text-purple-300 transition-colors">
                  Name of the product to scrape details?
                </label>
                <input
                  type="text"
                  name="productName"
                  value={formData.productName}
                  onChange={handleInputChange}
                  placeholder="Enter product name (one at a time)"
                  className="w-full p-4 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent transition-all duration-300 hover:bg-white/30"
                />
              </div>

              {/* Output Folder Input */}
              <div className="group">
                <label className="block text-white text-sm font-medium mb-2 group-hover:text-pink-300 transition-colors">
                  Folder in which you want to save the output and all images?
                </label>
                <input
                  type="text"
                  name="outputFolder"
                  value={formData.outputFolder}
                  onChange={handleInputChange}
                  placeholder="e.g., /downloads/scraped-data"
                  className="w-full p-4 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-pink-400 focus:border-transparent transition-all duration-300 hover:bg-white/30"
                />
              </div>

              {/* Recipient Email Input */}
              <div className="group">
                <label className="block text-white text-sm font-medium mb-2 group-hover:text-red-300 transition-colors">
                  Recipient email to which mail should be sent?
                </label>
                <input
                  type="email"
                  name="recipientEmail"
                  value={formData.recipientEmail}
                  onChange={handleInputChange}
                  placeholder="Enter email address"
                  className="w-full p-4 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-red-400 focus:border-transparent transition-all duration-300 hover:bg-white/30"
                />
              </div>

              {/* Start Button */}
              <div className="pt-4">
                <button
                  onClick={handleStart}
                  disabled={isProcessing}
                  className="w-full bg-gradient-to-r from-blue-500 via-purple-500 to-red-500 hover:from-blue-600 hover:via-purple-600 hover:to-red-600 text-white font-bold py-4 px-8 rounded-xl transition-all duration-300 transform hover:scale-105 hover:shadow-2xl disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                >
                  {isProcessing ? (
                    <div className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-2"></div>
                      Processing...
                    </div>
                  ) : (
                    'Start Scraping'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chatbot */}
      <div className="fixed bottom-8 right-8 z-50">
        {/* Gradient Circle Background */}
        <div className="absolute inset-0 bg-gradient-to-r from-blue-400 via-purple-400 to-red-400 rounded-full animate-pulse opacity-75 scale-110"></div>
        
        {/* Chatbot Button */}
        <div className="relative">
          <button
            onClick={toggleChatbot}
            className="w-20 h-20 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full shadow-2xl hover:scale-110 transition-transform duration-300 flex items-center justify-center group"
          >
            <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center">
              <Image
                src="/Live chatbot.gif"
                alt="AI Chatbot"
                width={48}
                height={48}
                className="rounded-full"
              />
            </div>
          </button>
        </div>

        {/* Chatbot Modal */}
        {chatbot.isOpen && (
          <div className="absolute bottom-24 right-0 w-96 bg-white/95 backdrop-blur-lg rounded-2xl shadow-2xl border border-white/20 overflow-hidden animate-slide-up">
            {!chatbot.showDetails ? (
              <div className="p-6">
                <div className="flex items-center mb-4">
                                     <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-blue-700 rounded-full flex items-center justify-center mr-3">
                    <Image
                      src="/Live chatbot.gif"
                      alt="AI Agent"
                      width={32}
                      height={32}
                      className="rounded-full"
                    />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800">AI Agent Assistant</h3>
                    <div className="flex items-center">
                      <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                      <span className="text-sm text-green-600">Online</span>
                    </div>
                  </div>
                </div>
                
                                 <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4 mb-4 border border-blue-200">
                   <p className="text-blue-900 text-sm leading-relaxed">
                     Hi! I am an intelligent, automated AI agent designed to streamline and enhance the process of validating digital purchase information from different shopping sites. I have <span className="font-bold text-blue-700">5 agents</span> working in the backend.
                   </p>
                 </div>
                
                <div className="text-center">
                  <p className="text-gray-600 text-sm mb-3">Want to know more?</p>
                                     <button
                     onClick={showDetails}
                     className="bg-gradient-to-r from-blue-500 to-blue-700 text-white px-6 py-2 rounded-lg hover:shadow-lg hover:from-blue-600 hover:to-blue-800 transition-all duration-300 transform hover:scale-105 shadow-blue-500/30"
                   >
                    <span className="flex items-center">
                      Learn More
                      <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-6 max-h-96 overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-gray-800">How I Work</h3>
                  <button
                    onClick={backToMain}
                    className="text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                
                <div className="space-y-4 text-sm text-gray-700">
                  <div className="border-l-4 border-blue-500 pl-4 py-2 bg-blue-50 rounded-r-lg">
                    <h4 className="font-semibold text-blue-700 mb-1">🔗 Purchase Link Scraping</h4>
                    <p>The AI initiates its process by intelligently scraping designated online purchase links. This involves navigating to the provided URL and extracting relevant content, preparing it for subsequent analysis.</p>
                  </div>
                  
                  <div className="border-l-4 border-purple-500 pl-4 py-2 bg-purple-50 rounded-r-lg">
                    <h4 className="font-semibold text-purple-700 mb-1">🖼️ Image Extraction & Processing</h4>
                    <p>From the scraped web pages, the system identifies and extracts all embedded images. These images are then queued for advanced processing.</p>
                  </div>
                  
                  <div className="border-l-4 border-green-500 pl-4 py-2 bg-green-50 rounded-r-lg">
                    <h4 className="font-semibold text-green-700 mb-1">👁️ Optical Character Recognition (OCR)</h4>
                    <p>Utilizing state-of-the-art OCR technology, the AI meticulously scans each extracted image to identify and extract any embedded text.</p>
                  </div>
                  
                  <div className="border-l-4 border-red-500 pl-4 py-2 bg-red-50 rounded-r-lg">
                    <h4 className="font-semibold text-red-700 mb-1">📱 QR Code Validation</h4>
                    <p>A critical component is its ability to detect and validate QR codes present within the extracted images. The AI performs robust validation checks for legitimacy and structural integrity.</p>
                  </div>
                  
                  <div className="border-l-4 border-yellow-500 pl-4 py-2 bg-yellow-50 rounded-r-lg">
                    <h4 className="font-semibold text-yellow-700 mb-1">📧 Automated Notification</h4>
                    <p>Upon completion of the validation process, the AI automatically triggers an email notification, ensuring immediate communication of the validation outcome.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
