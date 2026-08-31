import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { adminApi } from '../api';
import { useBranding } from '../hooks/useBranding';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { data: branding } = useBranding(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await adminApi.login(values.username, values.password);
      localStorage.setItem('admin_token', data.token);
      message.success('登录成功');
      navigate('/');
    } catch {
      message.error('用户名或密码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-bg login-page">
      <div className="login-card">
        {branding?.admin_logo && (
          <img src={branding.admin_logo} alt="" className="login-card__logo" />
        )}
        <h1 className="login-card__title">{branding?.login_title || 'NDS 管理面板'}</h1>
        <Form onFinish={onFinish} layout="vertical" size="large">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password placeholder="请输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      </div>
    </div>
  );
}
