import { DislikeOutlined, LikeOutlined } from '@ant-design/icons';
import { Button, Input, Modal, Select, Space, message } from 'antd';
import { useState } from 'react';

import { normalizeAccessToken } from '../api/auth';

export function FeedbackActions({
  accessToken,
  sessionId,
  turnId,
}: {
  accessToken: string;
  sessionId: string;
  turnId: string;
}) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState('INCORRECT');
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState<'UP' | 'DOWN' | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (rating: 'UP' | 'DOWN') => {
    setSubmitting(true);
    try {
      const response = await fetch('/api/v1/feedback', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `feedback-${turnId}`,
        },
        body: JSON.stringify({
          sessionId,
          turnId,
          rating,
          category: rating === 'DOWN' ? category : 'HELPFUL',
          comment: comment.trim() || null,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setSubmitted(rating);
      setOpen(false);
      message.success('反馈已记录，感谢你的帮助');
    } catch {
      message.error('反馈提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Space size={4} className="feedback-actions">
        <span>这个回答有帮助吗？</span>
        <Button
          type={submitted === 'UP' ? 'primary' : 'text'}
          size="small"
          icon={<LikeOutlined />}
          disabled={Boolean(submitted)}
          onClick={() => void submit('UP')}
          aria-label="回答有帮助"
        />
        <Button
          danger={submitted === 'DOWN'}
          type={submitted === 'DOWN' ? 'primary' : 'text'}
          size="small"
          icon={<DislikeOutlined />}
          disabled={Boolean(submitted)}
          onClick={() => setOpen(true)}
          aria-label="回答需要纠正"
        />
      </Space>
      <Modal
        open={open}
        title="提交答案纠错"
        okText="提交反馈"
        cancelText="取消"
        confirmLoading={submitting}
        onCancel={() => setOpen(false)}
        onOk={() => void submit('DOWN')}
      >
        <Select
          value={category}
          onChange={setCategory}
          style={{ width: '100%', marginBottom: 12 }}
          options={[
            { value: 'INCORRECT', label: '内容不正确' },
            { value: 'OUTDATED', label: '知识已过时' },
            { value: 'MISSING_CITATION', label: '缺少引用来源' },
            { value: 'UNSAFE', label: '存在医疗安全风险' },
            { value: 'OTHER', label: '其他问题' },
          ]}
        />
        <Input.TextArea
          rows={4}
          maxLength={2000}
          showCount
          value={comment}
          placeholder="请描述需要纠正的内容"
          onChange={(event) => setComment(event.target.value)}
        />
      </Modal>
    </>
  );
}
