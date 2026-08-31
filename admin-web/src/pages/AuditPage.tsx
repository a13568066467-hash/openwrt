import { Table } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import PageShell from '../components/PageShell';

export default function AuditPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: () => adminApi.getAuditLogs().then(r => r.data),
  });

  return (
    <PageShell title="审计日志">
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '操作', dataIndex: 'action' },
          { title: '目标类型', dataIndex: 'target_type' },
          { title: '目标ID', dataIndex: 'target_id' },
          { title: '详情', dataIndex: 'detail', ellipsis: true },
          { title: '时间', dataIndex: 'created_at' },
        ]}
      />
    </PageShell>
  );
}
