import { useState } from 'react';
import { Form, Input, Button, Toast, Card } from 'antd-mobile';
import { useQueryClient } from '@tanstack/react-query';
import { userApi, formatBytes } from '../api';

export default function RechargePage() {
  const qc = useQueryClient();
  const [loading, setLoading] = useState(false);

  const handleRedeem = async (values: { code: string }) => {
    setLoading(true);
    try {
      const { data } = await userApi.redeemVoucher(values.code.trim());
      Toast.show({ icon: 'success', content: `充值成功！余额 ${formatBytes(data.balance_bytes)}` });
      qc.invalidateQueries({ queryKey: ['profile'] });
    } catch {
      Toast.show({ icon: 'fail', content: '卡密无效或已使用' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <Card title="卡密充值">
        <p style={{ color: '#999', marginBottom: 16, fontSize: 14 }}>
          请输入购买的卡密进行充值，每个卡密仅可使用一次
        </p>
        <Form onFinish={handleRedeem} footer={
          <Button block type="submit" color="primary" loading={loading} size="large">
            立即充值
          </Button>
        }>
          <Form.Item name="code" rules={[{ required: true, message: '请输入卡密' }]}>
            <Input placeholder="请输入卡密" style={{ fontFamily: 'monospace', fontSize: 18, letterSpacing: 2 }} />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
