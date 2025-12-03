import { useState, useEffect, useRef } from 'react';
import Comment from './Comment';
import { api } from '../api';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  onReply,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleReply = async (content, persona) => {
    if (!conversation?.id) return;
    try {
      await api.sendReply(conversation.id, content, persona);
      if (onReply) onReply();
    } catch (error) {
      console.error("Failed to send reply:", error);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Hydra</h2>
          <p>Ask a question to summon the Council.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface forum-view">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a Discussion</h2>
            <p>Ask a question. The Chairman will assemble a team of experts.</p>
          </div>
        ) : (
          <>
            {/* Render first user message as Thread Starter (OP) */}
            {conversation.messages[0] && conversation.messages[0].role === 'user' && (
              <div className="thread-starter">
                <Comment
                  author="You"
                  icon="👤"
                  content={conversation.messages[0].content}
                  isOp={true}
                  votes={1}
                />
              </div>
            )}

            {/* Render all subsequent messages as comments */}
            {conversation.messages.slice(1).map((msg, index) => {
              const actualIndex = index + 1; // Adjust index since we sliced

              if (msg.role === 'user') {
                // User replies appear as regular comments
                return (
                  <div key={actualIndex} className="thread-comments">
                    <Comment
                      author="You"
                      icon="👤"
                      content={msg.content}
                      isOp={true}
                      votes={1}
                    />
                  </div>
                );
              } else if (msg.role === 'assistant') {
                // Assistant message containing stages
                return (
                  <div key={actualIndex} className="thread-comments">
                    {/* Loading State for Personas */}
                    {msg.loading?.stage1 && !msg.stage1 && (
                      <div className="loading-status">
                        <div className="spinner"></div>
                        <span>The Chairman is assembling the council...</span>
                      </div>
                    )}

                    {/* Stage 3: Chairman's Synthesis (Pinned) */}
                    {msg.stage3 && (
                      <div className="pinned-comment">
                        <div className="pinned-label">📌 Pinned by Moderators</div>
                        <Comment
                          author={msg.stage3.model}
                          role="Chairman"
                          icon="⚖️"
                          content={msg.stage3.response}
                          isMod={true}
                          votes={100}
                        />
                      </div>
                    )}

                    {/* Stage 1: Expert Responses */}
                    {msg.stage1 && msg.stage1.map((resp, i) => (
                      <Comment
                        key={i}
                        author={resp.persona_name || resp.model}
                        role={resp.persona_role}
                        icon={resp.persona_icon}
                        content={resp.response}
                        votes={Math.floor(Math.random() * 20) + 5}
                        onReply={(content) => handleReply(content, {
                          name: resp.persona_name,
                          role: resp.persona_role,
                          icon: resp.persona_icon,
                          model: resp.model,
                          system_prompt: resp.system_prompt || ""
                        })}
                        persona={{
                          name: resp.persona_name,
                          role: resp.persona_role,
                          icon: resp.persona_icon,
                          model: resp.model,
                          system_prompt: resp.system_prompt || ""
                        }}
                      />
                    ))}
                  </div>
                );
              }
              return null;
            })}
          </>
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Processing...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Ask a question to start a thread..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Post
        </button>
      </form>
    </div>
  );
}
