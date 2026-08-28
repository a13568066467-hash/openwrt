import { useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, message, Popconfirm } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, Plan } from '../api';

export default function PlansPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Plan | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => adminApi.getPlans().then(r => r.data),
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (plan: Plan) => {
    setEditing(plan);
    form.setFieldsValue(plan);
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    if (editing) {
      await adminApi.updatePlan(editing.id, values);
    } else {
      await adminApi.createPlan(values);
    }
    message.success('保存成功');
    setModalOpen(false);
    qc.invalidateQueries({ queryKey: ['plans'] });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>套餐管理</h2>
        <Button type="primary" onClick={openCreate}>新增套餐</Button>
      </div>
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '流量 (MB)', dataIndex: 'traffic_mb' },
          { title: '价格 (元)', dataIndex: 'price_cents', render: (v: number) => (v / 100).toFixed(2) },
          { title: '上行 (kbps)', dataIndex: 'upload_rate_kbps' },
          { title: '下行 (kbps)', dataIndex: 'download_rate_kbps' },
          { title: '状态', dataIndex: 'active', render: (v: boolean) => v ? '启用' : '禁用' },
          {
            title: '操作',
            render: (_: unknown, r: Plan) => (
              <>
                <Button size="small" onClick={() => openEdit(r)}>编辑</Button>
                <Popconfirm title="确认删除?" onConfirm={async () => {
                  await adminApi.deletePlan(r.id);
                  qc.invalidateQueries({ queryKey: ['plans'] });
                }}>
                  <Button size="small" danger style={{ marginLeft: 8 }}>删除</Button>
                </Popconfirm>
              </>
            ),
          },
        ]}
      />

      <Modal title={editing ? '编辑套餐' : '新增套餐'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="traffic_mb" label="流量 (MB)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={1} /></Form.Item>
          <Form.Item name="price_cents" label="价格 (分)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
          <Form.Item name="upload_rate_kbps" label="上行 (kbps)"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
          <Form.Item name="download_rate_kbps" label="下行 (kbps)"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
