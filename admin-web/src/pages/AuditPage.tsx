import { Table } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';

export default function AuditPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: () => adminApi.getAuditLogs().then(r => r.data),
  });

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>审计日志</h2>
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '操作', dataIndex: 'action' },
          { title: '目标类型', dataIndex: 'target_type' },
          { title: '目标ID', dataIndex: 'target_id' },
          { title: '详情', dataIndex: 'detail', ellipsis: true },
          { title: '时间', dataIndex: 'created_at' },
        ]}
      />
    </div>
  );
}
