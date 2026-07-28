import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import { Badge, Button, Empty, Popover, Spin } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import { normalizeAccessToken } from '../api/auth';

interface Notice {
  id: number;
  type: string;
  title: string;
  content: string;
  targetUrl?: string;
  readAt?: string;
  createdAt: string;
}

export function NotificationCenter({ accessToken }: { accessToken: string }) {
  const [items, setItems] = useState<Notice[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const headers = {
    Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
    'Content-Type': 'application/json',
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [listResponse, countResponse] = await Promise.all([
        fetch('/api/v1/notifications?size=20', { headers }),
        fetch('/api/v1/notifications/unread-count', { headers }),
      ]);
      if (listResponse.ok) {
        const payload = await listResponse.json();
        setItems(payload.data.content ?? []);
      }
      if (countResponse.ok) {
        const payload = await countResponse.json();
        setUnread(Number(payload.data ?? 0));
      }
    } finally {
      setLoading(false);
    }
  // The normalized token is stable for the life of the unlocked workspace.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  useEffect(() => { void load(); }, [load]);

  const markRead = async (notice: Notice) => {
    if (notice.readAt) return;
    const response = await fetch(`/api/v1/notifications/${notice.id}/read`, { method: 'PATCH', headers });
    if (response.ok) await load();
  };

  const content = (
    <div className="notification-panel">
      <div className="notification-panel__heading"><strong>通知中心</strong><span>{unread} 条未读</span></div>
      <Spin spinning={loading}>
        {items.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" /> : items.map((notice) => (
          <button
            key={notice.id}
            className={`notification-item ${notice.readAt ? '' : 'notification-item--unread'}`}
            onClick={() => void markRead(notice)}
          >
            <span><strong>{notice.title}</strong><small>{notice.content}</small></span>
            {notice.readAt ? <CheckOutlined /> : <i />}
          </button>
        ))}
      </Spin>
    </div>
  );

  return (
    <Popover trigger="click" placement="bottomRight" content={content} onOpenChange={(open) => { if (open) void load(); }}>
      <Badge count={unread} size="small">
        <Button type="text" shape="circle" icon={<BellOutlined />} aria-label="通知" />
      </Badge>
    </Popover>
  );
}
