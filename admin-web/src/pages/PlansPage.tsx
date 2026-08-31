import { useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, message, Popconfirm } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, Plan } from '../api';
import PageShell from '../components/PageShell';

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
    form.setFieldsValue({
      ...plan,
      price_yuan: plan.price_cents / 100,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    const { price_yuan, ...rest } = values;
    const payload = {
      ...rest,
      price_cents: Math.round(price_yuan * 100),
    };
    if (editing) {
      await adminApi.updatePlan(editing.id, payload);
    } else {
      await adminApi.createPlan(payload);
    }
    message.success('保存成功');
    setModalOpen(false);
    qc.invalidateQueries({ queryKey: ['plans'] });
  };

  return (
    <PageShell
      title="套餐管理"
      extra={<Button type="primary" onClick={openCreate}>新增套餐</Button>}
    >
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: '排序', dataIndex: 'sort_order', width: 72 },
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
                <Button size="small" type="link" onClick={() => openEdit(r)}>编辑</Button>
                <Popconfirm title="确认删除?" onConfirm={async () => {
                  await adminApi.deletePlan(r.id);
                  qc.invalidateQueries({ queryKey: ['plans'] });
                }}>
                  <Button size="small" type="link" danger>删除</Button>
                </Popconfirm>
              </>
            ),
          },
        ]}
      />

      <Modal title={editing ? '编辑套餐' : '新增套餐'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="sort_order" label="显示排序" tooltip="数字越小越靠前，如套餐一=1、套餐二=2">
            <InputNumber style={{ width: '100%' }} min={1} precision={0} />
          </Form.Item>
          <Form.Item name="traffic_mb" label="流量 (MB)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={1} /></Form.Item>
          <Form.Item name="price_yuan" label="价格 (元)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} step={0.01} precision={2} />
          </Form.Item>
          <Form.Item name="upload_rate_kbps" label="上行 (kbps)"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
          <Form.Item name="download_rate_kbps" label="下行 (kbps)"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
