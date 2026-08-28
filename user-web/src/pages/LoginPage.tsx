import { useState } from 'react';
import { Form, Input, Button, Tabs, Toast } from 'antd-mobile';
import { useNavigate } from 'react-router-dom';
import { userApi } from '../api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await userApi.login(values.username, values.password);
      localStorage.setItem('user_token', data.token);
      Toast.show({ icon: 'success', content: '登录成功' });
      navigate('/');
    } catch {
      Toast.show({ icon: 'fail', content: '登录失败' });
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await userApi.register(values.username, values.password);
      localStorage.setItem('user_token', data.token);
      Toast.show({ icon: 'success', content: '注册成功，赠送100MB' });
      navigate('/');
    } catch {
      Toast.show({ icon: 'fail', content: '注册失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, paddingTop: 80 }}>
      <h1 style={{ textAlign: 'center', marginBottom: 32, fontSize: 28 }}>流量充值</h1>
      <Tabs>
        <Tabs.Tab title="登录" key="login">
          <Form onFinish={handleLogin} footer={
            <Button block type="submit" color="primary" loading={loading} size="large">登录</Button>
          }>
            <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
              <Input placeholder="请输入用户名" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true }]}>
              <Input type="password" placeholder="请输入密码" />
            </Form.Item>
          </Form>
        </Tabs.Tab>
        <Tabs.Tab title="注册" key="register">
          <Form onFinish={handleRegister} footer={
            <Button block type="submit" color="primary" loading={loading} size="large">注册</Button>
          }>
            <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
              <Input placeholder="设置用户名" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true }]}>
              <Input type="password" placeholder="设置密码" />
            </Form.Item>
          </Form>
        </Tabs.Tab>
      </Tabs>
    </div>
  );
}
