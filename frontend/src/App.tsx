import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import VoiceAnalysisApp from './VoiceAnalysisApp';
import SurveyPage from './pages/SurveyPage';
import './App.css';

function App() {
  return (
    <div className="App">
      <Router basename="/tonebridge-app">
        <Routes>
          <Route path="/" element={<VoiceAnalysisApp />} />
          <Route path="/survey" element={<SurveyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App;
