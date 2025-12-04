import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Stage 1: Expert Perspectives</h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {resp.persona_icon} {resp.persona_name || resp.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">
          <span className="persona-icon-large">{responses[activeTab].persona_icon}</span>
          {responses[activeTab].persona_name || responses[activeTab].model}
          <span className="model-detail">({responses[activeTab].model.split('/')[1] || responses[activeTab].model})</span>
        </div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
