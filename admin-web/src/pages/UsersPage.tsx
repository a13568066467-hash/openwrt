import { useState } from 'react';
import { Table, Button, Modal, Form, InputNumber, Input, message, Tag } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, formatMB } from '../api';
import PageShell from '../components/PageShell';

export default function UsersPage() {
  const qc = useQueryClient();
  const [quotaModal, setQuotaModal] = useState<number | null>(null);
  const [rateModal, setRateModal] = useState<number | null>(null);
  const [quotaForm] = Form.useForm();
  const [rateForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => adminApi.getUsers().then(r => r.data),
  });

  const handleQuota = async () => {
    const values = await quotaForm.validateFields();
    await adminApi.adjustQuota(quotaModal!, values.amount_mb, values.note || '');
    message.success('额度已调整');
    setQuotaModal(null);
    qc.invalidateQueries({ queryKey: ['users'] });
  };

  const handleRate = async () => {
    const values = await rateForm.validateFields();
    await adminApi.updateRate(rateModal!, values.upload_rate_kbps, values.download_rate_kbps);
    message.success('限速已更新');
    setRateModal(null);
    qc.invalidateQueries({ queryKey: ['users'] });
  };

  return (
    <PageShell title="用户管理">
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '用户名', dataIndex: 'username' },
          {
            title: '剩余流量',
            dataIndex: 'quota_remaining_bytes',
            render: (v: number) => formatMB(v),
          },
          {
            title: '限速',
            render: (_: unknown, r) => `${r.upload_rate_kbps || 0}/${r.download_rate_kbps || 0} kbps`,
          },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s: string) => <Tag color={s === 'active' ? 'success' : 'error'}>{s}</Tag>,
          },
          {
            title: '操作',
            render: (_: unknown, r) => (
              <>
                <Button size="small" type="link" onClick={() => { setQuotaModal(r.id); quotaForm.resetFields(); }}>
                  调整流量
                </Button>
                <Button size="small" type="link" onClick={() => { setRateModal(r.id); rateForm.resetFields(); }}>
                  调整限速
                </Button>
              </>
            ),
          },
        ]}
      />

      <Modal title="调整流量 (MB)" open={quotaModal !== null} onOk={handleQuota} onCancel={() => setQuotaModal(null)}>
        <Form form={quotaForm} layout="vertical">
          <Form.Item name="amount_mb" label="调整量 (正数充值, 负数扣减)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="调整限速" open={rateModal !== null} onOk={handleRate} onCancel={() => setRateModal(null)}>
        <Form form={rateForm} layout="vertical">
          <Form.Item name="upload_rate_kbps" label="上行 (kbps)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
          <Form.Item name="download_rate_kbps" label="下行 (kbps)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
