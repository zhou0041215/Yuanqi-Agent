import { ArrowRightOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, message } from 'antd';
import { useState } from 'react';

interface Props {
  onUnlock: (token: string) => void;
}

export function TokenGate({ onUnlock }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [pendingToken, setPendingToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username.trim() || !password) return;
    setLoading(true);
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await readResponse(response);
      if (!response.ok) throw new Error(data.message || `后端返回 HTTP ${response.status}`);
      const token = data.data?.accessToken as string | undefined;
      if (!token) throw new Error('登录响应中缺少访问令牌');
      if (data.data.mustChangePassword) {
        setPendingToken(token);
      } else {
        onUnlock(token);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async () => {
    if (newPassword !== confirmation) {
      message.error('两次输入的新密码不一致');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch('/api/v1/auth/change-password', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${pendingToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ currentPassword: password, newPassword }),
      });
      const data = await readResponse(response);
      if (!response.ok) throw new Error(data.message || `后端返回 HTTP ${response.status}`);
      message.success('密码已更新，请使用新密码重新登录');
      setPendingToken('');
      setPassword('');
      setNewPassword('');
      setConfirmation('');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '密码修改失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="token-gate">
      <aside className="token-identity" aria-label="元启医学智能协作台">
        <div>
          <div className="token-mark" aria-hidden="true">元</div>
          <p className="token-system">YUANQI / MEDICAL OS</p>
          <h1>元启<br />医学智能协作台</h1>
          <p className="token-identity-copy">面向医学知识探索与受控业务协作的可信工作空间。</p>
        </div>
        <div className="token-trace" aria-label="访问流程">
          <div><span>01</span><strong>验证身份</strong></div>
          <div><span>02</span><strong>加载数据范围</strong></div>
          <div><span>03</span><strong>进入工作台</strong></div>
        </div>
      </aside>

      <section className="token-access" aria-labelledby="token-title">
        <div className="token-access-header">
          <SafetyCertificateOutlined />
          <span>受控访问</span>
        </div>
        <div className="token-form">
          <p className="eyebrow">SESSION ACCESS</p>
          <h2 id="token-title">进入工作台</h2>
          <p className="token-copy">请输入账号和密码。首次登录必须设置新的强密码。</p>
          <label htmlFor="username">账号</label>
          <Input id="username" size="large" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          <label htmlFor="password">密码</label>
          <Input.Password id="password" size="large" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" onPressEnter={handleLogin} />
          <Button className="token-submit" type="primary" size="large" block icon={<ArrowRightOutlined />} loading={loading} onClick={handleLogin}>
            进入协作台
          </Button>
          <p className="token-note">生产环境应接入医院统一认证；开发令牌接口仅在 dev 环境启用。</p>
        </div>
      </section>

      <Modal
        title="首次登录：设置新密码"
        open={Boolean(pendingToken)}
        closable={false}
        maskClosable={false}
        okText="更新密码"
        cancelButtonProps={{ style: { display: 'none' } }}
        confirmLoading={loading}
        onOk={handlePasswordChange}
      >
        <p>新密码至少 10 位，并包含大写字母、小写字母、数字和符号。</p>
        <Form layout="vertical">
          <Form.Item label="新密码">
            <Input.Password value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" />
          </Form.Item>
          <Form.Item label="确认新密码">
            <Input.Password value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" onPressEnter={handlePasswordChange} />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  );
}

async function readResponse(response: Response) {
  const contentType = response.headers.get('content-type') || '';
  return contentType.includes('application/json')
    ? response.json()
    : { message: await response.text() };
}
