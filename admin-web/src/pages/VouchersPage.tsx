import { useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, message, Tag } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

export default function VouchersPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['voucher-batches'],
    queryFn: () => adminApi.getVoucherBatches().then(r => r.data),
  });

  const handleCreate = async () => {
    const values = await form.validateFields();
    const { data: result } = await adminApi.createVoucherBatch(values.name, values.traffic_mb, values.count);
    setCodes(result.codes);
    message.success(`已生成 ${result.codes.length} 张卡密`);
    qc.invalidateQueries({ queryKey: ['voucher-batches'] });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>卡密管理</h2>
        <Button type="primary" onClick={() => { form.resetFields(); setCodes([]); setModalOpen(true); }}>
          生成卡密批次
        </Button>
      </div>
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '批次名称', dataIndex: 'name' },
          { title: '面额 (MB)', dataIndex: 'traffic_mb' },
          { title: '数量', dataIndex: 'count' },
          { title: '创建时间', dataIndex: 'created_at' },
        ]}
      />

      <Modal
        title="生成卡密批次"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="批次名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="traffic_mb" label="面额 (MB)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={1} /></Form.Item>
          <Form.Item name="count" label="数量" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={1} max={1000} /></Form.Item>
        </Form>
        {codes.length > 0 && (
          <div style={{ marginTop: 16, maxHeight: 200, overflow: 'auto', background: '#f5f5f5', padding: 12, borderRadius: 8 }}>
            <Tag color="orange">请立即保存，卡密仅显示一次</Tag>
            {codes.map(c => <div key={c} style={{ fontFamily: 'monospace' }}>{c}</div>)}
          </div>
        )}
      </Modal>
    </div>
  );
}
