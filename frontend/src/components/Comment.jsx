import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Comment.css';

function Comment({ author, role, icon, content, isOp = false, isMod = false, votes = 0, onReply, persona }) {
    const [isReplying, setIsReplying] = useState(false);
    const [replyContent, setReplyContent] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleReplySubmit = async () => {
        if (!replyContent.trim()) return;

        setIsSubmitting(true);
        try {
            await onReply(replyContent, persona);
            setIsReplying(false);
            setReplyContent('');
        } catch (error) {
            console.error("Reply failed", error);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className={`comment ${isOp ? 'op-comment' : ''} ${isMod ? 'mod-comment' : ''}`}>
            <div className="comment-sidebar">
                <div className="vote-arrows">
                    <button className="upvote">▲</button>
                    <span className="vote-count">{votes || Math.floor(Math.random() * 50) + 1}</span>
                    <button className="downvote">▼</button>
                </div>
            </div>
            <div className="comment-main">
                <div className="comment-header">
                    <span className="comment-icon">{icon || '👤'}</span>
                    <span className="comment-author">{author}</span>
                    {role && <span className="comment-flair">{role}</span>}
                    {isOp && <span className="flair-op">OP</span>}
                    {isMod && <span className="flair-mod">MOD</span>}
                    <span className="comment-time">just now</span>
                </div>
                <div className="comment-body markdown-content">
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
                <div className="comment-footer">
                    <button onClick={() => setIsReplying(!isReplying)}>Reply</button>
                    <button>Share</button>
                    <button>Report</button>
                </div>

                {isReplying && (
                    <div className="reply-input-container">
                        <textarea
                            value={replyContent}
                            onChange={(e) => setReplyContent(e.target.value)}
                            placeholder="Write your reply..."
                            rows={3}
                            disabled={isSubmitting}
                        />
                        <div className="reply-actions">
                            <button
                                className="cancel-button"
                                onClick={() => setIsReplying(false)}
                                disabled={isSubmitting}
                            >
                                Cancel
                            </button>
                            <button
                                className="submit-button"
                                onClick={handleReplySubmit}
                                disabled={!replyContent.trim() || isSubmitting}
                            >
                                {isSubmitting ? 'Posting...' : 'Reply'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default Comment;
